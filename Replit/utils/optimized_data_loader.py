"""
Optimized data loading utilities for improved performance in the financial dashboard.
This module provides functions to speed up data loading and initialization.
"""

import streamlit as st
import time
import logging
import pandas as pd
from functools import lru_cache
from data_processor import FinancialDataProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OptimizedDataLoader:
    """
    Optimized data loader class that manages data processor initialization
    and provides caching and performance improvements.
    """
    
    def __init__(self):
        """Initialize the optimized data loader."""
        self._data_processor = None
        logger.info("OptimizedDataLoader initialized")
        
    def get_data_processor(self):
        """Get or initialize the data processor instance."""
        if self._data_processor is None:
            start_time = time.time()
            self._data_processor = FinancialDataProcessor()
            self._data_processor.load_data()
            initialization_time = time.time() - start_time
            logger.info(f"Data processor initialized in {initialization_time:.2f} seconds")
        return self._data_processor
        
    def preload_frequent_data(self):
        """Preload frequently accessed data to improve performance."""
        start_time = time.time()
        logger.info("Preloading frequently accessed data...")
        
        # Get the data processor
        processor = self.get_data_processor()
        
        # Cache common company lookups
        top_companies = ["Apple", "Microsoft", "Alphabet", "Amazon", "Meta Platforms"]
        common_years = [2021, 2022, 2023, 2024]
        
        # Pre-warm the cache
        for company in top_companies:
            for year in common_years:
                processor.get_metrics(company, year)
                processor.get_segments(company, year)
                
        # Force evaluation of lazy-loaded properties
        processor.get_companies()
        
        preload_time = time.time() - start_time
        logger.info(f"Preloaded frequently accessed data in {preload_time:.2f} seconds")

@st.cache_resource(ttl=3600*4)
def get_data_processor():
    """Get or initialize the data processor with caching."""
    start_time = time.time()
    processor = FinancialDataProcessor()
    initialization_time = time.time() - start_time
    logger.info(f"Data processor initialized in {initialization_time:.2f} seconds")
    
    # Preload frequently accessed data in the background
    preload_frequently_accessed_data(processor)
    
    return processor
    
def preload_frequently_accessed_data(processor):
    """Preload frequently accessed data to improve performance."""
    start_time = time.time()
    logger.info("Preloading frequently accessed data...")
    
    # Cache common company lookups
    top_companies = ["Apple", "Microsoft", "Alphabet", "Amazon", "Meta Platforms"]
    common_years = [2021, 2022, 2023, 2024]
    
    # Pre-warm the cache
    for company in top_companies:
        for year in common_years:
            processor.get_metrics(company, year)
            processor.get_segments(company, year)
            
    # Force evaluation of lazy-loaded properties
    processor.get_companies()
    
    preload_time = time.time() - start_time
    logger.info(f"Preloaded frequently accessed data in {preload_time:.2f} seconds")

@lru_cache(maxsize=128)
def get_cached_metrics(company, year, processor_id=None):
    """Get cached metrics for a company and year."""
    processor = get_data_processor()
    return processor.get_metrics(company, year)

@lru_cache(maxsize=32)
def get_cached_company_list(processor_id=None):
    """Get cached list of companies."""
    processor = get_data_processor()
    return processor.get_companies()

@lru_cache(maxsize=32) 
def get_cached_available_years(company, processor_id=None):
    """Get cached list of available years for a company."""
    processor = get_data_processor()
    return processor.get_available_years(company)

def load_data_for_year(year, companies, processor_id=None):
    """Load data for a specific year and set of companies."""
    processor = get_data_processor()
    result = {}
    
    for company in companies:
        try:
            metrics = processor.get_metrics(company, year)
            if metrics:
                if year not in result:
                    result[year] = []
                result[year].append(metrics)
        except Exception as e:
            logger.error(f"Error loading data for {company}, {year}: {e}")
            
    return result