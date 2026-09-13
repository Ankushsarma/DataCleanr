from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import polars as pl
import pandas as pd
import os
from app.db.session import get_db
from app.db.models import Dataset, Job
from imblearn.over_sampling import SMOTE

router = APIRouter()

class BalanceRequest(BaseModel):
    target_column: str

@router.post("/{dataset_id}/balance")
async def apply_balancing(dataset_id: str, request: BalanceRequest, db = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    encoded_path = os.path.join("local_storage/transformed", f"{dataset_id}_encoded.csv")
    cleaned_path = os.path.join("local_storage/transformed", f"{dataset_id}_cleaned.csv")
    
    file_path = encoded_path if os.path.exists(encoded_path) else cleaned_path
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=400, detail="Data must be cleaned/encoded before balancing.")
        
    # SMOTE works best with pandas/scikit-learn
    df_pandas = pd.read_csv(file_path)
    
    target_col = request.target_column
    if target_col not in df_pandas.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' not found.")
        
    # Check if target is numeric/encoded
    if not pd.api.types.is_numeric_dtype(df_pandas[target_col]):
        raise HTTPException(status_code=400, detail=f"Target column '{target_col}' must be numeric. Ensure it has been encoded first.")
        
    # Separate features and target
    X = df_pandas.drop(columns=[target_col])
    y = df_pandas[target_col]
    
    # Check if we can apply SMOTE (needs numeric features)
    non_numeric_cols = X.select_dtypes(exclude=['number']).columns.tolist()
    if non_numeric_cols:
        raise HTTPException(
            status_code=400, 
            detail=f"SMOTE requires all features to be numeric. Please encode the following columns first: {non_numeric_cols}"
        )
        
    # Check for missing values
    if X.isnull().sum().sum() > 0 or y.isnull().sum() > 0:
        raise HTTPException(status_code=400, detail="Dataset contains missing values. Run cleaning pipeline first.")
        
    try:
        # Apply SMOTE
        smote = SMOTE(random_state=42)
        X_resampled, y_resampled = smote.fit_resample(X, y)
        
        # Combine back
        df_balanced = pd.concat([X_resampled, y_resampled], axis=1)
        
        # Convert back to Polars for consistency and saving
        lf_balanced = pl.from_pandas(df_balanced)
        
        balanced_path = os.path.join("local_storage/transformed", f"{dataset_id}_balanced.csv")
        lf_balanced.write_csv(balanced_path)
        
        # Track applied operations in Job
        job = db.query(Job).filter(Job.dataset_id == dataset_id).first()
        if job:
            old_size = len(df_pandas)
            new_size = len(df_balanced)
            job.applied_operations = job.applied_operations + [f"Balanced: SMOTE applied on '{target_col}' (Rows: {old_size} -> {new_size})"]
            db.commit()
            
        return {
            "message": "Dataset successfully balanced using SMOTE.",
            "balanced_file": balanced_path,
            "original_rows": len(df_pandas),
            "balanced_rows": len(df_balanced)
        }
        
    except ValueError as e:
        # Happens if there's only 1 class or too few samples for SMOTE neighbors
        raise HTTPException(status_code=400, detail=f"SMOTE failed: {str(e)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
