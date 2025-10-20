from google.cloud import bigquery
from google.cloud.exceptions import NotFound
import os
from datetime import datetime
import json

class BigQueryService:
    def __init__(self):
        """Initialize BigQuery client"""
        self.client = bigquery.Client()
        self.project_id = "lexical-theory-471417-q3"  # Your Firebase project ID
        self.dataset_id = "wanderly_analytics"
        self.dataset_ref = self.client.dataset(self.dataset_id, project=self.project_id)
        
        # Create dataset if it doesn't exist
        try:
            self.client.get_dataset(self.dataset_ref)
        except NotFound:
            dataset = bigquery.Dataset(self.dataset_ref)
            dataset.description = "Wanderly travel planning analytics data"
            dataset = self.client.create_dataset(dataset)
    
    def create_tables(self):
        """Create all necessary tables for analytics"""
        
        # User Analytics Table
        user_analytics_schema = [
            bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("email", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("last_active", "TIMESTAMP", mode="NULLABLE"),
            bigquery.SchemaField("total_groups", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("total_rooms_completed", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("preferred_destinations", "STRING", mode="REPEATED"),
        ]
        
        # Group Analytics Table
        group_analytics_schema = [
            bigquery.SchemaField("group_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("group_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("destination", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("start_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("end_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("member_count", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("rooms_count", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("completion_rate", "FLOAT", mode="REQUIRED"),
        ]
        
        # Room Analytics Table
        room_analytics_schema = [
            bigquery.SchemaField("room_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("group_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("room_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("completed_at", "TIMESTAMP", mode="NULLABLE"),
            bigquery.SchemaField("questions_count", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("answers_count", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("suggestions_count", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("votes_count", "INTEGER", mode="REQUIRED"),
            bigquery.SchemaField("completion_time_hours", "FLOAT", mode="NULLABLE"),
        ]
        
        # Answer Analytics Table
        answer_analytics_schema = [
            bigquery.SchemaField("answer_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("room_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("question_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("question_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("answer_value", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("answer_text", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("min_value", "INTEGER", mode="NULLABLE"),
            bigquery.SchemaField("max_value", "INTEGER", mode="NULLABLE"),
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        
        # Vote Analytics Table
        vote_analytics_schema = [
            bigquery.SchemaField("vote_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("suggestion_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("vote_type", "STRING", mode="REQUIRED"),  # 'thumbs_up' or 'thumbs_down'
            bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        ]
        
        tables = [
            ("user_analytics", user_analytics_schema),
            ("group_analytics", group_analytics_schema),
            ("room_analytics", room_analytics_schema),
            ("answer_analytics", answer_analytics_schema),
            ("vote_analytics", vote_analytics_schema),
        ]
        
        for table_name, schema in tables:
            table_id = f"{self.project_id}.{self.dataset_id}.{table_name}"
            table_ref = bigquery.Table(table_id, schema=schema)
            
            try:
                self.client.get_table(table_ref)
                pass
            except NotFound:
                table = self.client.create_table(table_ref)
    
    def insert_user_analytics(self, user_data):
        """Insert user analytics data"""
        table_id = f"{self.project_id}.{self.dataset_id}.user_analytics"
        table = self.client.get_table(table_id)
        
        row = {
            "user_id": user_data["id"],
            "email": user_data["email"],
            "name": user_data["name"],
            "created_at": datetime.utcnow().isoformat(),
            "last_active": datetime.utcnow().isoformat(),
            "total_groups": 0,
            "total_rooms_completed": 0,
            "preferred_destinations": [],
        }
        
        errors = self.client.insert_rows_json(table, [row])
        if errors:
            pass
        return len(errors) == 0
    
    def insert_group_analytics(self, group_data):
        """Insert group analytics data"""
        table_id = f"{self.project_id}.{self.dataset_id}.group_analytics"
        table = self.client.get_table(table_id)
        
        row = {
            "group_id": group_data["id"],
            "group_name": group_data["group_name"],
            "destination": group_data["destination"],
            "start_date": group_data["start_date"],
            "end_date": group_data["end_date"],
            "created_at": datetime.utcnow().isoformat(),
            "member_count": len(group_data.get("members", [])),
            "rooms_count": 0,
            "completion_rate": 0.0,
        }
        
        errors = self.client.insert_rows_json(table, [row])
        if errors:
        return len(errors) == 0
    
    def insert_room_analytics(self, room_data):
        """Insert room analytics data"""
        table_id = f"{self.project_id}.{self.dataset_id}.room_analytics"
        table = self.client.get_table(table_id)
        
        row = {
            "room_id": room_data["id"],
            "group_id": room_data["group_id"],
            "room_type": room_data["room_type"],
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "questions_count": 0,
            "answers_count": 0,
            "suggestions_count": 0,
            "votes_count": 0,
            "completion_time_hours": None,
        }
        
        errors = self.client.insert_rows_json(table, [row])
        if errors:
        return len(errors) == 0
    
    def insert_answer_analytics(self, answer_data):
        """Insert answer analytics data"""
        table_id = f"{self.project_id}.{self.dataset_id}.answer_analytics"
        table = self.client.get_table(table_id)
        
        row = {
            "answer_id": answer_data["id"],
            "room_id": answer_data["room_id"],
            "user_id": answer_data["user_id"],
            "question_id": answer_data["question_id"],
            "question_type": answer_data.get("question_type", "unknown"),
            "answer_value": str(answer_data.get("answer_value", "")),
            "answer_text": answer_data.get("answer_text", ""),
            "min_value": answer_data.get("min_value"),
            "max_value": answer_data.get("max_value"),
            "created_at": datetime.utcnow().isoformat(),
        }
        
        errors = self.client.insert_rows_json(table, [row])
        if errors:
        return len(errors) == 0
    
    def insert_vote_analytics(self, vote_data):
        """Insert vote analytics data"""
        table_id = f"{self.project_id}.{self.dataset_id}.vote_analytics"
        table = self.client.get_table(table_id)
        
        row = {
            "vote_id": vote_data["id"],
            "suggestion_id": vote_data["suggestion_id"],
            "user_id": vote_data["user_id"],
            "vote_type": vote_data["vote_type"],
            "created_at": datetime.utcnow().isoformat(),
        }
        
        errors = self.client.insert_rows_json(table, [row])
        if errors:
        return len(errors) == 0
    
    def get_popular_destinations(self, limit=10):
        """Get most popular destinations"""
        query = f"""
        SELECT 
            destination,
            COUNT(*) as group_count,
            AVG(member_count) as avg_members,
            AVG(completion_rate) as avg_completion_rate
        FROM `{self.project_id}.{self.dataset_id}.group_analytics`
        GROUP BY destination
        ORDER BY group_count DESC
        LIMIT {limit}
        """
        
        query_job = self.client.query(query)
        results = query_job.result()
        return [dict(row) for row in results]
    
    def get_user_engagement_stats(self):
        """Get user engagement statistics"""
        query = f"""
        SELECT 
            COUNT(*) as total_users,
            AVG(total_groups) as avg_groups_per_user,
            AVG(total_rooms_completed) as avg_rooms_per_user,
            COUNT(CASE WHEN last_active >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY) THEN 1 END) as active_last_week,
            COUNT(CASE WHEN last_active >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY) THEN 1 END) as active_last_month
        FROM `{self.project_id}.{self.dataset_id}.user_analytics`
        """
        
        query_job = self.client.query(query)
        results = query_job.result()
        return dict(list(results)[0])
    
    def get_room_completion_analysis(self):
        """Get room completion analysis"""
        query = f"""
        SELECT 
            room_type,
            COUNT(*) as total_rooms,
            COUNT(completed_at) as completed_rooms,
            AVG(completion_time_hours) as avg_completion_time,
            AVG(questions_count) as avg_questions,
            AVG(suggestions_count) as avg_suggestions
        FROM `{self.project_id}.{self.dataset_id}.room_analytics`
        GROUP BY room_type
        ORDER BY total_rooms DESC
        """
        
        query_job = self.client.query(query)
        results = query_job.result()
        return [dict(row) for row in results]

# Global BigQuery service instance
bigquery_service = BigQueryService()
