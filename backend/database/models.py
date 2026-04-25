"""
Database models and query builders
"""

from typing import Any, Dict, List, Optional
from decimal import Decimal
from datetime import datetime
from client import DataAPIClient


class BaseModel:
    """Base class for database models"""
    
    table_name = None
    
    def __init__(self, db: DataAPIClient):
        self.db = db
        if not self.table_name:
            raise ValueError("table_name must be defined")
    
    def find_by_id(self, id: Any) -> Optional[Dict]:
        """Find a record by ID"""
        sql = f"SELECT * FROM {self.table_name} WHERE id = :id::uuid"
        return self.db.query_one(sql, [{'name': 'id', 'value': {'stringValue': str(id)}}])
    
    def find_all(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Find all records with pagination"""
        sql = f"SELECT * FROM {self.table_name} LIMIT :limit OFFSET :offset"
        params = [
            {'name': 'limit', 'value': {'longValue': limit}},
            {'name': 'offset', 'value': {'longValue': offset}}
        ]
        return self.db.query(sql, params)
    
    def create(self, data: Dict, returning: str = 'id') -> str:
        """Create a new record"""
        return self.db.insert(self.table_name, data, returning=returning)
    
    def update(self, id: Any, data: Dict) -> int:
        """Update a record by ID"""
        return self.db.update(self.table_name, data, "id = :id::uuid", {'id': str(id)})
    
    def delete(self, id: Any) -> int:
        """Delete a record by ID"""
        return self.db.delete(self.table_name, "id = :id::uuid", {'id': str(id)})


class Users(BaseModel):
    """Users table operations"""
    table_name = 'users'
    
    def find_by_clerk_id(self, clerk_user_id: str) -> Optional[Dict]:
        """Find user by Clerk ID"""
        sql = f"SELECT * FROM {self.table_name} WHERE clerk_user_id = :clerk_id"
        params = [{'name': 'clerk_id', 'value': {'stringValue': clerk_user_id}}]
        return self.db.query_one(sql, params)
    
    def create_user(self, clerk_user_id: str, display_name: str = None, 
        years_until_retirement: int = None, target_retirement_income: Decimal = None) -> str:
        """Create a new user"""
        data = {
            'clerk_user_id': clerk_user_id,
            'display_name': display_name,
            'years_until_retirement': years_until_retirement,
            'target_retirement_income': target_retirement_income
        }
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}
        return self.db.insert(self.table_name, data, returning='clerk_user_id')

class Consultations(BaseModel):
    """Legal consultations table operations"""
    table_name = 'consultations'
    
    def create_consultation(self, user_id: str, consultation_date: datetime, consultation_type: str, consultation_report: str, consultation_notes: str) -> str:
        """Create a new consultation"""
        data = {
            'user_id': user_id,
            'consultation_date': consultation_date.isoformat(),
            'consultation_type': consultation_type,
            'consultation_report': consultation_report,
            'consultation_notes': consultation_notes
        }
        return self.db.insert(self.table_name, data, returning='id')