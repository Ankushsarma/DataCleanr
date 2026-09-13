from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Any
import polars as pl
import os
import io
import base64
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from app.db.session import get_db
from app.db.models import Dataset

router = APIRouter()

@router.get("/{dataset_id}/eda")
def get_eda(dataset_id: str, state: str = "raw", db = Depends(get_db)):
    """
    Returns EDA visualizations data (distributions, correlation matrix).
    state can be 'raw', 'cleaned', or 'encoded'.
    """
    dataset = db.query(Dataset).filter(Dataset.dataset_id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    # Determine which file to read based on the requested state
    if state == "raw":
        file_path = os.path.join("local_storage/raw", f"{dataset_id}.csv")
    elif state == "cleaned":
        file_path = os.path.join("local_storage/transformed", f"{dataset_id}_cleaned.csv")
    elif state == "encoded":
        # Check if a balanced dataset exists first, otherwise use encoded
        balanced_path = os.path.join("local_storage/transformed", f"{dataset_id}_balanced.csv")
        encoded_path = os.path.join("local_storage/transformed", f"{dataset_id}_encoded.csv")
        file_path = balanced_path if os.path.exists(balanced_path) else encoded_path
    else:
        raise HTTPException(status_code=400, detail="Invalid state parameter. Use 'raw', 'cleaned', or 'encoded'.")
        
    if not os.path.exists(file_path):
        # Fallback to the previous state if the requested one doesn't exist yet
        if state == "encoded":
            file_path = os.path.join("local_storage/transformed", f"{dataset_id}_cleaned.csv")
            if not os.path.exists(file_path):
                file_path = os.path.join("local_storage/raw", f"{dataset_id}.csv")
        elif state == "cleaned":
            file_path = os.path.join("local_storage/raw", f"{dataset_id}.csv")
            
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found on disk")
            
    try:
        df = pl.read_csv(file_path, ignore_errors=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read dataset: {str(e)}")
        
    response_data = {
        "distributions_image": None,
        "heatmap_image": None
    }
    
    numeric_cols = [col for col in df.columns if df[col].dtype in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]]
    
    # Generate Distributions Image
    if numeric_cols:
        try:
            n_cols = len(numeric_cols)
            cols_per_row = 3
            rows = math.ceil(n_cols / cols_per_row)
            
            fig, axes = plt.subplots(rows, cols_per_row, figsize=(15, 4 * rows))
            if rows * cols_per_row > 1:
                axes = axes.flatten()
            else:
                axes = [axes]
                
            for i, col in enumerate(numeric_cols):
                data = df.select(pl.col(col)).drop_nulls().to_series().to_list()
                axes[i].hist(data, bins=20, color='skyblue', edgecolor='black')
                axes[i].set_title(col)
                
            for j in range(len(numeric_cols), len(axes)):
                axes[j].set_visible(False)
                
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format='png', facecolor='white')
            plt.close(fig)
            buf.seek(0)
            response_data["distributions_image"] = base64.b64encode(buf.read()).decode('utf-8')
        except Exception as e:
            print(f"Failed to generate distributions image: {e}")
            
    # Generate Heatmap Image
    if len(numeric_cols) > 1:
        try:
            corr_df = df.select(numeric_cols).corr()
            fig = plt.figure(figsize=(10, 8))
            sns.heatmap(
                corr_df.to_pandas(), 
                xticklabels=numeric_cols, 
                yticklabels=numeric_cols, 
                annot=True, 
                cmap='coolwarm', 
                fmt=".2f"
            )
            plt.title("Correlation Heatmap")
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format='png', facecolor='white')
            plt.close(fig)
            buf.seek(0)
            response_data["heatmap_image"] = base64.b64encode(buf.read()).decode('utf-8')
        except Exception as e:
            print(f"Failed to generate correlation matrix: {e}")
            
    return response_data
