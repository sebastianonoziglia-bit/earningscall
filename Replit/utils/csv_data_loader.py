"""
CSV Data Loader for AI Assistant

This module loads data from CSV files and caches them for the AI assistant to access.
It provides a more direct access to project data without requiring database queries.
"""

import os
import pandas as pd
import glob
import json
import logging
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CSVDataLoader:
    """
    Loads and caches CSV data for AI Assistant to use
    """
    def __init__(self):
        self.data_cache = {}
        self.attached_assets_dir = "attached_assets"
        self.data_dir = "data"
        
        # Mapping of common CSV file patterns to dataset names
        self.file_patterns = {
            "Global Stock Market Value*.csv": "global_market_data",
            "*Financial*.csv": "financial_data",
            "*Financial*.xlsx": "financial_data_excel",
            "*Advertising*.csv": "advertising_data",
            "*Advertising*.xlsx": "advertising_data_excel",
            "*Acquisitions*.csv": "acquisitions_data",
            "*Stock*.csv": "stock_data",
            "Segmenti*.csv": "segment_data",
        }
        
        # Load all available data
        self.load_all_data()
    
    def load_all_data(self):
        """Load all relevant CSV files"""
        logger.info("Loading CSV data for AI assistant...")
        
        # Load from attached_assets directory
        for pattern, dataset_name in self.file_patterns.items():
            pattern_path = os.path.join(self.attached_assets_dir, pattern)
            matching_files = glob.glob(pattern_path)
            
            if matching_files:
                logger.info(f"Found {len(matching_files)} files matching {pattern}")
                # Take the first file for simplicity
                file_path = matching_files[0]
                self._load_file(file_path, dataset_name)
        
        # Load from data directory if it exists
        if os.path.exists(self.data_dir):
            for pattern, dataset_name in self.file_patterns.items():
                pattern_path = os.path.join(self.data_dir, pattern)
                matching_files = glob.glob(pattern_path)
                
                if matching_files:
                    logger.info(f"Found {len(matching_files)} files matching {pattern} in data directory")
                    # Take the first file for simplicity
                    file_path = matching_files[0]
                    self._load_file(file_path, dataset_name)
        
        logger.info(f"Loaded {len(self.data_cache)} datasets")
    
    def _load_file(self, file_path, dataset_name):
        """Load a file into the data cache"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.csv':
                # Try different encodings - UTF-8 first, then latin-1
                try:
                    df = pd.read_csv(file_path, encoding='utf-8')
                except UnicodeDecodeError:
                    df = pd.read_csv(file_path, encoding='latin-1')
                
                self.data_cache[dataset_name] = df
                logger.info(f"Loaded CSV dataset '{dataset_name}' with {len(df)} rows")
            
            elif file_ext in ['.xlsx', '.xls']:
                # For Excel files, load all sheets
                excel_file = pd.ExcelFile(file_path)
                sheet_names = excel_file.sheet_names
                
                # Store each sheet separately
                for sheet in sheet_names:
                    sheet_name = f"{dataset_name}_{sheet.lower().replace(' ', '_')}"
                    df = pd.read_excel(file_path, sheet_name=sheet)
                    self.data_cache[sheet_name] = df
                    logger.info(f"Loaded Excel sheet '{sheet_name}' with {len(df)} rows")
        
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {str(e)}")
    
    def get_dataset_summary(self):
        """Get summary information about available datasets"""
        summary = {}
        
        for dataset_name, df in self.data_cache.items():
            summary[dataset_name] = {
                "rows": len(df),
                "columns": list(df.columns),
                "sample": df.head(2).to_dict(orient='records')
            }
        
        return summary
    
    def get_dataset(self, dataset_name):
        """Get a specific dataset by name"""
        if dataset_name in self.data_cache:
            return self.data_cache[dataset_name]
        return None
    
    def query_dataset(self, dataset_name, query_params):
        """
        Query a dataset based on column-value pairs
        
        Args:
            dataset_name: Name of the dataset to query
            query_params: Dict of column-value pairs to filter by
        
        Returns:
            Filtered DataFrame or None if not found
        """
        if dataset_name not in self.data_cache:
            return None
        
        df = self.data_cache[dataset_name]
        
        # Apply filters
        for column, value in query_params.items():
            if column in df.columns:
                df = df[df[column] == value]
        
        return df
    
    def search_all_datasets(self, search_term):
        """
        Search across all datasets for a specific term
        
        Args:
            search_term: String to search for
        
        Returns:
            Dict of dataset_name -> matching rows
        """
        results = {}
        
        for dataset_name, df in self.data_cache.items():
            # Convert all columns to string type for searching
            str_df = df.astype(str)
            
            # Find rows that contain the search term in any column
            mask = str_df.apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
            matching_rows = df[mask]
            
            if len(matching_rows) > 0:
                results[dataset_name] = matching_rows.to_dict(orient='records')
        
        return results
    
    def get_company_data(self, company_name):
        """
        Get all data for a specific company across all datasets
        
        Args:
            company_name: Name of the company to search for
        
        Returns:
            Dict of dataset information for the company
        """
        company_data = {}
        
        # Try various column names that might contain company information
        company_columns = ['Company', 'company', 'company_name', 'Name', 'name']
        
        for dataset_name, df in self.data_cache.items():
            # Find a matching company column
            matching_company_col = None
            for col in company_columns:
                if col in df.columns:
                    matching_company_col = col
                    break
            
            if matching_company_col:
                # Look for exact matches first
                company_rows = df[df[matching_company_col] == company_name]
                
                # If no exact matches, try case-insensitive contains
                if len(company_rows) == 0:
                    mask = df[matching_company_col].str.contains(company_name, case=False, na=False)
                    company_rows = df[mask]
                
                if len(company_rows) > 0:
                    company_data[dataset_name] = company_rows.to_dict(orient='records')
        
        return company_data

# Singleton instance
_csv_data_loader = None

def get_csv_data_loader():
    """Get singleton instance of CSVDataLoader"""
    global _csv_data_loader
    if _csv_data_loader is None:
        _csv_data_loader = CSVDataLoader()
    return _csv_data_loader