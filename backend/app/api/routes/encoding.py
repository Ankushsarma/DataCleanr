from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import polars as pl
import os
import json
import uuid

from app.db.session import get_db
from app.db.models import Dataset
from app.services.llm import GeminiLLMProvider
from app.core.config import settings
from app.models.ir import TransformationIR, Scope, Constraints, AllowedOperation
from app.services.compiler import IRCompiler

router = APIRouter()

class EncodeAnalyzeResponse(BaseModel):
    columns: List[Dict[str, Any]]

class EncodeApplyRequest(BaseModel):
    target_column_name: Optional[str] = None

@router.get("/{dataset_id}/encoding/analyze", response_model=EncodeAnalyzeResponse)
def analyze_encoding(dataset_id: str, db = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    # We will read the cleaned dataset if it exists, otherwise the raw dataset
    cleaned_path = os.path.join("local_storage/transformed", f"{dataset_id}_cleaned.csv")
    raw_path = os.path.join("local_storage/raw", f"{dataset_id}.csv")
    
    file_path = cleaned_path if os.path.exists(cleaned_path) else raw_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
        
    df = pl.read_csv(file_path, ignore_errors=True)
    columns_data = []
    
    for col_name in df.columns:
        series = df[col_name]
        # Only analyze strings or categoricals
        if series.dtype == pl.String or series.dtype == pl.Categorical:
            unique_vals = series.drop_nulls().unique().to_list()
            # If there are too many unique values, it's probably not categorical, 
            # but we return up to 20 for the user to decide
            if len(unique_vals) <= 20:
                columns_data.append({
                    "column": col_name,
                    "unique_count": len(unique_vals),
                    "unique_values": unique_vals,
                    "dtype": str(series.dtype)
                })
                
    return {"columns": columns_data}

@router.post("/{dataset_id}/encoding/apply")
async def apply_encoding(dataset_id: str, request: EncodeApplyRequest, db = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    cleaned_path = os.path.join("local_storage/transformed", f"{dataset_id}_cleaned.csv")
    raw_path = os.path.join("local_storage/raw", f"{dataset_id}.csv")
    file_path = cleaned_path if os.path.exists(cleaned_path) else raw_path
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
        
    df = pl.read_csv(file_path, ignore_errors=True)
    context_lines = []
    
    for col_name in df.columns:
        series = df[col_name]
        if series.dtype == pl.String or series.dtype == pl.Categorical:
            unique_vals = series.drop_nulls().unique().to_list()
            # Only consider columns with reasonable number of unique values for encoding
            if len(unique_vals) <= 20:
                context_lines.append(f"Column '{col_name}': {len(unique_vals)} unique values -> {str(unique_vals[:10])}")
            
    if not context_lines:
        raise HTTPException(status_code=400, detail="No string columns suitable for encoding found.")
        
    target_info = ""
    if request.target_column_name:
        target_info = f"\nThe user has selected '{request.target_column_name}' as the target variable for Target Encoding."
        
    prompt = f"""
    The user wants to encode the following string/categorical columns automatically. 
    Context:
    {chr(10).join(context_lines)}
    {target_info}
    
    For EACH column listed above, choose the BEST encoding strategy from this list:
    - ONE_HOT_ENCODE (best if unique values < 5 and no natural order)
    - LABEL_ENCODE (best if no specific order but you need integers)
    - ORDINAL_ENCODE (best if there is a natural logical order. You MUST provide the 'order' array in parameters)
    - TARGET_ENCODE (best if a target variable is provided and cardinality is high. You MUST provide 'target_variable' in parameters)
    - KEEP (if it's free text, an ID, or should not be encoded)
    
    Return a list of candidates where each candidate contains an IR for the operation. Do not return KEEP operations in the candidates.
    """
    
    schema = {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string"},
                        "target_column": {"type": "string"},
                        "rationale": {"type": "string"},
                        "risk_level": {"type": "string"},
                        "agent_confidence": {"type": "string"},
                        "parameters": {"type": "object"}
                    },
                    "required": ["operation", "target_column", "rationale", "risk_level", "agent_confidence"]
                }
            }
        },
        "required": ["candidates"]
    }
    
    system_prompt = (
        "You are an expert data engineer AI. Return ONLY a valid JSON object matching the provided JSON schema. "
        "No markdown wrapping. You must output an array of 'candidates' where each is a valid TransformationIR object. "
        "CRITICAL: Every candidate MUST include 'operation' (string), 'rationale' (1 short sentence), 'risk_level' (string: LOW, MEDIUM, or HIGH), "
        "and 'agent_confidence' (string: LOW, MEDIUM, or HIGH). "
        "Allowed operations: ONE_HOT_ENCODE, LABEL_ENCODE, ORDINAL_ENCODE, TARGET_ENCODE. "
        "Do NOT return KEEP operations. Do NOT perform any data cleaning operations like REGEX_REPLACE or IMPUTE_MEAN. "
        "Your sole task is to choose the best encoding strategy for each provided string column. Be extremely concise."
    )
    
    llm = GeminiLLMProvider(api_key=settings.GEMINI_API_KEY)
    response_text = await llm.complete(prompt=prompt, schema=schema, max_tokens=4000, system_prompt=system_prompt)
    
    try:
        raw_json = json.loads(response_text)
        candidates = raw_json.get("candidates", [])
    except json.JSONDecodeError as e:
        with open("llm_response_error.txt", "w") as f:
            f.write(response_text)
        print(f"JSONDecodeError: {e}, Response: {response_text}")
        raise HTTPException(status_code=500, detail="Failed to parse LLM response")
        
    lf = pl.scan_csv(file_path)
    operations_applied = []
    
    try:
        # Process IRs
        for cand in candidates:
            ir = TransformationIR(
                issue_id=str(uuid.uuid4()),
                operation=AllowedOperation(cand["operation"]),
                target_column=cand["target_column"],
                rationale=cand.get("rationale", ""),
                risk_level=cand.get("risk_level", "LOW"),
                agent_confidence=cand.get("agent_confidence", "HIGH"),
                parameters=cand.get("parameters", {}),
                scope=Scope(),
                constraints=Constraints(preserve_row_count=True)
            )
            lf = IRCompiler.compile(ir, lf)
            operations_applied.append(cand["operation"])
            
        # Final safeguard to ensure 0 missing values
        schema = lf.collect_schema()
        for col, dtype in schema.items():
            if dtype in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]:
                lf = lf.with_columns(pl.col(col).fill_null(pl.col(col).median()))
            elif dtype in [pl.String, pl.Categorical, pl.Utf8]:
                lf = lf.with_columns(pl.col(col).fill_null(pl.lit("Unknown")))
                
        encoded_path = os.path.join("local_storage/transformed", f"{dataset_id}_encoded.csv")
        lf.sink_csv(encoded_path)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to apply encoding operations: {str(e)}")
    
    return {
        "message": "Encoding applied successfully",
        "encoded_file": encoded_path,
        "operations": operations_applied
    }

@router.get("/{dataset_id}/encoding/download_encoded")
def download_encoded_dataset(dataset_id: str):
    file_path = os.path.join("local_storage/transformed", f"{dataset_id}_encoded.csv")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Encoded dataset not found.")
    
    return FileResponse(
        path=file_path,
        media_type="text/csv",
        filename=f"autoclean_{dataset_id[:8]}_encoded.csv"
    )
