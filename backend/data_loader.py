# backend/data_loader.py
"""
CSV data loader and normalizer for enriching Cassandra query results
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)

# Module-level variables for cached DataFrames
students_csv: Optional[pd.DataFrame] = None
subjects_csv: Optional[pd.DataFrame] = None

# Data directory configuration - Updated for Docker container
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))

def load_csv_data():
    """Load and cache CSV data on startup with column normalization"""
    global students_csv, subjects_csv
    
    try:
        logger.info(f"📂 Loading CSV data from: {DATA_DIR}")
        
        # Check if data directory exists
        if not DATA_DIR.exists():
            logger.error(f"❌ Data directory not found: {DATA_DIR}")
            return False
        
        # Load students CSV
        students_path = DATA_DIR / "students.csv"
        if students_path.exists():
            students_csv = pd.read_csv(students_path)
            logger.info(f"✅ Raw students.csv loaded: {len(students_csv)} rows, {len(students_csv.columns)} columns")
            
            # Normalize column names to lowercase and strip whitespace
            students_csv.columns = [c.strip().lower() for c in students_csv.columns]
            logger.debug(f"📋 Raw students columns: {list(students_csv.columns)}")
            
            # Rename common column variations to standard names
            column_mappings = {
                'studentid': 'id',
                'student_id': 'id',
                'studentno': 'id',
                'student_no': 'id',
                'userid': 'id',
                'user_id': 'id'
            }
            
            # Apply column renamings
            for old_name, new_name in column_mappings.items():
                if old_name in students_csv.columns:
                    students_csv = students_csv.rename(columns={old_name: new_name})
                    logger.info(f"🔄 Renamed column '{old_name}' → '{new_name}' in students CSV")
            
            # Verify required columns
            if 'id' not in students_csv.columns:
                logger.error("❌ Students CSV missing 'id' column after renaming")
                logger.error(f"Available columns: {list(students_csv.columns)}")
                return False
            
            # Convert id to numeric if possible
            try:
                students_csv['id'] = pd.to_numeric(students_csv['id'], errors='coerce')
                logger.debug("✅ Converted students 'id' column to numeric")
            except Exception as e:
                logger.warning(f"⚠️ Could not convert students 'id' to numeric: {e}")
            
            logger.info(f"✅ Students CSV processed: {len(students_csv)} rows, {len(students_csv.columns)} columns")
            logger.info(f"📋 Final students columns: {list(students_csv.columns)}")
            
            # Log sample data for verification (first 2 rows, key columns only)
            key_cols = ['id', 'name', 'programme', 'overallcgpa'] if all(col in students_csv.columns for col in ['id', 'name', 'programme', 'overallcgpa']) else students_csv.columns[:4]
            logger.debug(f"📊 Sample student data:\n{students_csv[key_cols].head(2).to_string()}")
        else:
            logger.warning(f"⚠️ Students CSV not found: {students_path}")
        
        # Load subjects CSV
        subjects_path = DATA_DIR / "subjects.csv"
        if subjects_path.exists():
            subjects_csv = pd.read_csv(subjects_path)
            logger.info(f"✅ Raw subjects.csv loaded: {len(subjects_csv)} rows, {len(subjects_csv.columns)} columns")
            
            # Normalize column names to lowercase and strip whitespace
            subjects_csv.columns = [c.strip().lower() for c in subjects_csv.columns]
            logger.debug(f"📋 Raw subjects columns: {list(subjects_csv.columns)}")
            
            # Rename common column variations to standard names
            column_mappings = {
                'studentid': 'id',
                'student_id': 'id',
                'studentno': 'id', 
                'student_no': 'id',
                'userid': 'id',
                'user_id': 'id',
                'subject': 'subjectname',
                'subject_name': 'subjectname',
                'coursename': 'subjectname',
                'course_name': 'subjectname',
                'modulename': 'subjectname',
                'module_name': 'subjectname'
            }
            
            # Apply column renamings
            for old_name, new_name in column_mappings.items():
                if old_name in subjects_csv.columns:
                    subjects_csv = subjects_csv.rename(columns={old_name: new_name})
                    logger.info(f"🔄 Renamed column '{old_name}' → '{new_name}' in subjects CSV")
            
            # Verify required columns
            required_cols = ['id', 'subjectname']
            missing_cols = [col for col in required_cols if col not in subjects_csv.columns]
            if missing_cols:
                logger.error(f"❌ Subjects CSV missing required columns after renaming: {missing_cols}")
                logger.error(f"Available columns: {list(subjects_csv.columns)}")
                return False
            
            # Convert id to numeric if possible
            try:
                subjects_csv['id'] = pd.to_numeric(subjects_csv['id'], errors='coerce')
                logger.debug("✅ Converted subjects 'id' column to numeric")
            except Exception as e:
                logger.warning(f"⚠️ Could not convert subjects 'id' to numeric: {e}")
            
            # Clean up subjectname (strip whitespace, handle nulls)
            subjects_csv['subjectname'] = subjects_csv['subjectname'].astype(str).str.strip()
            
            logger.info(f"✅ Subjects CSV processed: {len(subjects_csv)} rows, {len(subjects_csv.columns)} columns")
            logger.info(f"📋 Final subjects columns: {list(subjects_csv.columns)}")
            
            # Log sample data for verification (first 2 rows, key columns only)
            key_cols = ['id', 'subjectname', 'grade', 'overallpercentage'] if all(col in subjects_csv.columns for col in ['id', 'subjectname', 'grade', 'overallpercentage']) else subjects_csv.columns[:4]
            logger.debug(f"📊 Sample subject data:\n{subjects_csv[key_cols].head(2).to_string()}")
        else:
            logger.warning(f"⚠️ Subjects CSV not found: {subjects_path}")
        
        # Final validation
        csv_loaded = (students_csv is not None) or (subjects_csv is not None)
        if csv_loaded:
            logger.info("✅ CSV data loading completed successfully")
            
            # Log summary statistics
            if students_csv is not None:
                logger.info(f"📊 Students data: {len(students_csv):,} records")
            if subjects_csv is not None:
                logger.info(f"📊 Subjects data: {len(subjects_csv):,} records")
        else:
            logger.warning("⚠️ No CSV files were loaded")
        
        return csv_loaded
        
    except Exception as e:
        logger.error(f"❌ Failed to load CSV data: {e}", exc_info=True)
        return False

def normalize_students(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize/enrich student data by merging with CSV data
    
    Args:
        rows: List of student dictionaries from Cassandra
        
    Returns:
        List of enriched student dictionaries
    """
    if not rows or students_csv is None:
        return rows
    
    try:
        # Convert to DataFrame
        df = pd.DataFrame(rows)
        
        # Ensure id column exists and is the right type
        if 'id' not in df.columns:
            logger.warning("⚠️ No 'id' column in student rows, skipping normalization")
            return rows
        
        # Convert id to same type as CSV (usually int)
        df['id'] = pd.to_numeric(df['id'], errors='coerce')
        
        # Merge with CSV data (left join to preserve all Cassandra results)
        merged = df.merge(
            students_csv, 
            on="id", 
            how="left", 
            suffixes=("", "_csv")
        )
        
        # Fill missing values from CSV where Cassandra data is null/missing
        for col in students_csv.columns:
            if col != 'id' and col in merged.columns:
                csv_col = f"{col}_csv"
                if csv_col in merged.columns:
                    # Use CSV value where Cassandra value is null/empty
                    merged[col] = merged[col].fillna(merged[csv_col])
                    # Drop the duplicate CSV column
                    merged = merged.drop(columns=[csv_col])
        
        # Convert back to list of dictionaries
        result = merged.to_dict(orient="records")
        
        logger.debug(f"🔄 Normalized {len(rows)} student records")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error normalizing student data: {e}")
        return rows  # Return original data on error

def normalize_subjects(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize/enrich subject data by merging with CSV data
    
    Args:
        rows: List of subject dictionaries from Cassandra
        
    Returns:
        List of enriched subject dictionaries
    """
    if not rows or subjects_csv is None:
        return rows
    
    try:
        # Convert to DataFrame
        df = pd.DataFrame(rows)
        
        # Ensure required columns exist
        required_cols = ['id', 'subjectname']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logger.warning(f"⚠️ Missing columns {missing_cols} in subject rows, skipping normalization")
            return rows
        
        # Convert id to same type as CSV
        df['id'] = pd.to_numeric(df['id'], errors='coerce')
        
        # Merge with CSV data on both id and subjectname
        merged = df.merge(
            subjects_csv,
            on=["id", "subjectname"],
            how="left",
            suffixes=("", "_csv")
        )
        
        # Fill missing values from CSV where Cassandra data is null/missing
        for col in subjects_csv.columns:
            if col not in ['id', 'subjectname'] and col in merged.columns:
                csv_col = f"{col}_csv"
                if csv_col in merged.columns:
                    # Use CSV value where Cassandra value is null/empty
                    merged[col] = merged[col].fillna(merged[csv_col])
                    # Drop the duplicate CSV column
                    merged = merged.drop(columns=[csv_col])
        
        # Convert back to list of dictionaries
        result = merged.to_dict(orient="records")
        
        logger.debug(f"🔄 Normalized {len(rows)} subject records")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error normalizing subject data: {e}")
        return rows  # Return original data on error

def get_csv_status() -> Dict[str, Any]:
    """Get status of loaded CSV data"""
    return {
        "students_loaded": students_csv is not None,
        "subjects_loaded": subjects_csv is not None,
        "students_count": len(students_csv) if students_csv is not None else 0,
        "subjects_count": len(subjects_csv) if subjects_csv is not None else 0,
        "students_columns": list(students_csv.columns) if students_csv is not None else [],
        "subjects_columns": list(subjects_csv.columns) if subjects_csv is not None else [],
        "data_directory": str(DATA_DIR)
    }

def reload_csv_data():
    """Reload CSV data (useful for development)"""
    global students_csv, subjects_csv
    students_csv = None
    subjects_csv = None
    return load_csv_data()

# For backwards compatibility
def normalize_data(rows: List[Dict[str, Any]], table_type: str) -> List[Dict[str, Any]]:
    """
    Normalize data based on table type
    
    Args:
        rows: List of dictionaries from Cassandra
        table_type: "students" or "subjects"
        
    Returns:
        List of normalized dictionaries
    """
    if table_type == "students":
        return normalize_students(rows)
    elif table_type == "subjects":
        return normalize_subjects(rows)
    else:
        logger.warning(f"⚠️ Unknown table type for normalization: {table_type}")
        return rows