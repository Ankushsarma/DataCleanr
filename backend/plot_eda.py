import polars as pl
import matplotlib.pyplot as plt
import seaborn as sns
import sys
import os
import math

def generate_eda(csv_path, output_dir):
    print(f"Reading data from {csv_path}...")
    df = pl.read_csv(csv_path)
    
    # 1. Plot Distributions
    print("Generating distribution plots...")
    numeric_cols = df.select(pl.col(pl.NUMERIC_DTYPES)).columns
    n_cols = len(numeric_cols)
    cols_per_row = 3
    rows = math.ceil(n_cols / cols_per_row)
    
    fig, axes = plt.subplots(rows, cols_per_row, figsize=(15, 4 * rows))
    axes = axes.flatten()
    
    for i, col in enumerate(numeric_cols):
        # Drop nulls for plotting
        data = df.select(pl.col(col)).drop_nulls().to_series().to_list()
        axes[i].hist(data, bins=20, color='skyblue', edgecolor='black')
        axes[i].set_title(col)
        
    # Hide any unused subplots
    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)
        
    plt.tight_layout()
    dist_path = os.path.join(output_dir, "distributions.png")
    plt.savefig(dist_path)
    plt.close()
    print(f"Saved distributions to {dist_path}")
    
    # 2. Plot Correlation Heatmap
    print("Generating correlation heatmap...")
    # Polars correlation matrix
    corr_df = df.select(pl.col(pl.NUMERIC_DTYPES)).corr()
    
    plt.figure(figsize=(10, 8))
    # Convert Polars DataFrame to Pandas for Seaborn heatmap
    sns.heatmap(corr_df.to_pandas(), xticklabels=numeric_cols, yticklabels=numeric_cols, annot=True, cmap='coolwarm', fmt=".2f")
    plt.title("Correlation Heatmap")
    plt.tight_layout()
    
    heat_path = os.path.join(output_dir, "heatmap.png")
    plt.savefig(heat_path)
    plt.close()
    print(f"Saved heatmap to {heat_path}")

if __name__ == "__main__":
    csv_file = "d:/autoCleaner/autoclean_b0f182f3_encoded.csv"
    out_dir = "C:/Users/ankus/.gemini/antigravity-ide/brain/77345ed7-d4ca-4592-a0c5-5a8cce0cd664"
    generate_eda(csv_file, out_dir)
