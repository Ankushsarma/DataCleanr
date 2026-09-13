from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
import polars as pl
import pandas as pd
import os
from app.db.session import get_db
from app.db.models import Dataset, Job
from sklearn.preprocessing import StandardScaler, MinMaxScaler

router = APIRouter()

class ScaleRequest(BaseModel):
    target_columns: List[str]
    method: str = "Standard" # "Standard" or "MinMax"

@router.post("/{dataset_id}/scale")
async def apply_scaling(dataset_id: str, request: ScaleRequest, db = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    encoded_path = os.path.join("local_storage/transformed", f"{dataset_id}_encoded.csv")
    cleaned_path = os.path.join("local_storage/transformed", f"{dataset_id}_cleaned.csv")
    
    file_path = encoded_path if os.path.exists(encoded_path) else cleaned_path
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="Data must be cleaned/encoded before scaling.")
        
    df_pandas = pd.read_csv(file_path)
    
    # Check if all target columns exist and are numeric
    for col in request.target_columns:
        if col not in df_pandas.columns:
            raise HTTPException(status_code=400, detail=f"Column '{col}' not found.")
        if not pd.api.types.is_numeric_dtype(df_pandas[col]):
            raise HTTPException(status_code=400, detail=f"Column '{col}' must be numeric to scale.")
            
    # Apply Scaling
    try:
        if request.method == "Standard":
            scaler = StandardScaler()
            df_pandas[request.target_columns] = scaler.fit_transform(df_pandas[request.target_columns])
        elif request.method == "MinMax":
            scaler = MinMaxScaler()
            df_pandas[request.target_columns] = scaler.fit_transform(df_pandas[request.target_columns])
        else:
            raise HTTPException(status_code=400, detail=f"Unknown method {request.method}")
            
        lf_scaled = pl.from_pandas(df_pandas)
        scaled_path = os.path.join("local_storage/transformed", f"{dataset_id}_scaled.csv")
        lf_scaled.write_csv(scaled_path)
        
        job = db.query(Job).filter(Job.dataset_id == dataset_id).first()
        if job:
            job.applied_operations = job.applied_operations + [f"Scaled: {request.method} on {request.target_columns}"]
            db.commit()
            
        return {"message": f"Successfully scaled {len(request.target_columns)} columns."}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
