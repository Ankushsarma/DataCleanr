import os
import polars as pl
from typing import List
from app.models.ir import TransformationIR
from app.services.compiler import IRCompiler

class SandboxExecutor:
    """
    Executes compiled Polars operations on a dataset.
    For Stage 1 MVP, this runs locally. In Stage 2+, this would run inside a 
    containerized MicroVM or gVisor sandbox.
    """
    
    TRANSFORMED_DIR = "local_storage/transformed"
    
    @classmethod
    def setup(cls):
        os.makedirs(cls.TRANSFORMED_DIR, exist_ok=True)
        
    @classmethod
    def execute(cls, dataset_id: str, input_file_path: str, ir_list: List[TransformationIR]) -> str:
        cls.setup()
        
        try:
            print(f"[SandboxExecutor] Setting up execution environment for {dataset_id}")
            # 1. Read input as LazyFrame for out-of-core streaming execution
            lf = pl.scan_csv(input_file_path, null_values=["NA", "null", ""])
            
            # 2. Chain all transformations
            for ir in ir_list:
                print(f"[SandboxExecutor] Applying `{ir.operation.value}` to column '{ir.target_column}'")
                lf = IRCompiler.compile(ir, lf)
                
            # 3. FINAL PASS: Ensure 0 missing values unconditionally as requested.
            schema = lf.collect_schema()
            for col, dtype in schema.items():
                if dtype in [pl.Int64, pl.Float64, pl.Int32, pl.Float32]:
                    lf = lf.with_columns(pl.col(col).fill_null(pl.col(col).median()))
                elif dtype in [pl.String, pl.Categorical, pl.Utf8]:
                    lf = lf.with_columns(pl.col(col).fill_null(pl.lit("Unknown")))

            # 4. Execute the computation graph and write directly to the output file
            output_file_path = os.path.join(cls.TRANSFORMED_DIR, f"{dataset_id}_cleaned.csv")
            
            # .sink_csv executes the lazy graph and streams output without loading everything to RAM
            lf.sink_csv(output_file_path)
            
            return output_file_path
            
        except Exception as e:
            print(f"Sandbox Execution Error: {e}")
            raise e
