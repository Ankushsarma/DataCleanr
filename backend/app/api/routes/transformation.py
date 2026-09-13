from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
import polars as pl
import numpy as np
import pandas as pd
import os
from app.db.session import get_db
from app.db.models import Dataset, Job

router = APIRouter()

class TransformRequest(BaseModel):
    target_columns: List[str]
    method: str = "Log1p" # "Log1p" or "Sqrt"

def get_latest_file(dataset_id: str):
    stages = ["balanced", "transformed", "scaled", "encoded", "cleaned"]
    for stage in stages:
        path = os.path.join("local_storage/transformed", f"{dataset_id}_{stage}.csv")
        if os.path.exists(path):
            return path
    return None

@router.post("/{dataset_id}/transform")
async def apply_transformation(dataset_id: str, request: TransformRequest, db = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    file_path = get_latest_file(dataset_id)
    if not file_path:
        raise HTTPException(status_code=400, detail="Data must be cleaned before transformation.")
        
    df_pandas = pd.read_csv(file_path)
    
    for col in request.target_columns:
        if col not in df_pandas.columns:
            raise HTTPException(status_code=400, detail=f"Column '{col}' not found.")
        if not pd.api.types.is_numeric_dtype(df_pandas[col]):
            raise HTTPException(status_code=400, detail=f"Column '{col}' must be numeric to transform.")
            
    try:
        if request.method == "Log1p":
            for col in request.target_columns:
                # Need to handle negative values safely for log
                if df_pandas[col].min() < 0:
                    raise HTTPException(status_code=400, detail=f"Column '{col}' contains negative values, cannot apply Log transformation.")
                df_pandas[col] = np.log1p(df_pandas[col])
        elif request.method == "Sqrt":
            for col in request.target_columns:
                if df_pandas[col].min() < 0:
                    raise HTTPException(status_code=400, detail=f"Column '{col}' contains negative values, cannot apply Sqrt transformation.")
                df_pandas[col] = np.sqrt(df_pandas[col])
        else:
            raise HTTPException(status_code=400, detail=f"Unknown method {request.method}")
            
        lf_transformed = pl.from_pandas(df_pandas)
        transformed_path = os.path.join("local_storage/transformed", f"{dataset_id}_transformed.csv")
        lf_transformed.write_csv(transformed_path)
        
        job = db.query(Job).filter(Job.dataset_id == dataset_id).first()
        if job:
            job.applied_operations = job.applied_operations + [f"Transformed: {request.method} on {request.target_columns}"]
            db.commit()
            
        return {"message": f"Successfully transformed {len(request.target_columns)} columns."}
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
