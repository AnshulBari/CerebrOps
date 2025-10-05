"""
CerebrOps Anomaly Detection Module
Uses machine learning to detect anomalies in system metrics and logs
"""

import json
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta
import logging
import requests
import os
from typing import Dict, List, Tuple, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('anomaly_detector')

class AnomalyDetector:
    def __init__(self, contamination=0.1, app_url="http://localhost:5000"):
        """
        Initialize the anomaly detector
        
        Args:
            contamination (float): Expected proportion of anomalies in data
            app_url (str): URL of the Flask application
        """
        self.contamination = contamination
        self.app_url = app_url
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.feature_columns = [
            'cpu_usage', 'memory_usage', 'disk_usage', 
            'error_rate', 'request_count', 'response_time'
        ]
        
    def fetch_metrics_data(self) -> List[Dict]:
        """Fetch recent metrics from the Flask application"""
        try:
            response = requests.get(f"{self.app_url}/metrics", timeout=10)
            response.raise_for_status()
            return [response.json()]
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch metrics: {e}")
            # Return sample data for testing
            return self._generate_sample_data()
    
    def fetch_logs_data(self) -> List[Dict]:
        """Fetch recent logs from the Flask application"""
        try:
            response = requests.get(f"{self.app_url}/logs", timeout=10)
            response.raise_for_status()
            return response.json().get('logs', [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch logs: {e}")
            return []
    
    def _generate_sample_data(self) -> List[Dict]:
        """Generate sample data for training and testing"""
        np.random.seed(42)
        data = []
        
        # Generate normal data
        for i in range(100):
            data.append({
                'timestamp': (datetime.now() - timedelta(hours=i)).isoformat(),
                'cpu_usage': np.random.normal(50, 10),
                'memory_usage': np.random.normal(60, 8),
                'disk_usage': np.random.normal(70, 5),
                'error_rate': np.random.normal(2, 1),
                'request_count': np.random.normal(100, 20),
                'response_time': np.random.normal(0.5, 0.2)
            })
        
        # Generate some anomalous data
        for i in range(10):
            data.append({
                'timestamp': (datetime.now() - timedelta(hours=i*5)).isoformat(),
                'cpu_usage': np.random.normal(90, 5),  # High CPU
                'memory_usage': np.random.normal(85, 5),  # High memory
                'disk_usage': np.random.normal(95, 2),  # High disk
                'error_rate': np.random.normal(15, 3),  # High error rate
                'request_count': np.random.normal(200, 30),  # High requests
                'response_time': np.random.normal(2.0, 0.5)  # Slow response
            })
        
        return data
    
    def prepare_features(self, data: List[Dict]) -> pd.DataFrame:
        """Prepare features for machine learning model"""
        df = pd.DataFrame(data)
        
        # Ensure all required columns exist
        for col in self.feature_columns:
            if col not in df.columns:
                df[col] = 0
        
        # Fill missing values
        df[self.feature_columns] = df[self.feature_columns].fillna(0)
        
        # Add time-based features
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['hour'] = df['timestamp'].dt.hour
            df['day_of_week'] = df['timestamp'].dt.dayofweek
            self.feature_columns.extend(['hour', 'day_of_week'])
        
        return df[self.feature_columns]
    
    def train_model(self, training_data: List[Dict] = None) -> bool:
        """
        Train the anomaly detection model
        
        Args:
            training_data: List of metric dictionaries for training
            
        Returns:
            bool: True if training successful
        """
        try:
            if training_data is None:
                logger.info("No training data provided, using sample data")
                training_data = self._generate_sample_data()
            
            logger.info(f"Training model with {len(training_data)} data points")
            
            # Prepare features
            features_df = self.prepare_features(training_data)
            
            if features_df.empty:
                logger.error("No valid features found in training data")
                return False
            
            # Scale features
            features_scaled = self.scaler.fit_transform(features_df)
            
            # Train model
            self.model.fit(features_scaled)
            self.is_trained = True
            
            logger.info("Model training completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Model training failed: {e}")
            return False
    
    def detect_anomalies(self, data: List[Dict]) -> Dict[str, Any]:
        """
        Detect anomalies in the provided data
        
        Args:
            data: List of metric dictionaries to analyze
            
        Returns:
            Dict containing anomaly detection results
        """
        if not self.is_trained:
            logger.warning("Model not trained, training with sample data first")
            if not self.train_model():
                return {'status': 'error', 'message': 'Failed to train model'}
        
        try:
            if not data:
                logger.warning("No data provided for anomaly detection")
                return {'status': 'no_data', 'message': 'No data to analyze'}
            
            # Prepare features
            features_df = self.prepare_features(data)
            
            if features_df.empty:
                return {'status': 'error', 'message': 'No valid features found'}
            
            # Scale features
            features_scaled = self.scaler.transform(features_df)
            
            # Predict anomalies
            predictions = self.model.predict(features_scaled)
            anomaly_scores = self.model.decision_function(features_scaled)
            
            # Analyze results
            anomaly_count = np.sum(predictions == -1)
            total_count = len(predictions)
            anomaly_percentage = (anomaly_count / total_count) * 100
            
            # Get anomalous data points
            anomalous_indices = np.where(predictions == -1)[0]
            anomalous_data = [data[i] for i in anomalous_indices if i < len(data)]
            
            result = {
                'status': 'anomaly' if anomaly_count > 0 else 'normal',
                'timestamp': datetime.now().isoformat(),
                'total_data_points': total_count,
                'anomaly_count': int(anomaly_count),
                'anomaly_percentage': round(anomaly_percentage, 2),
                'anomalous_data': anomalous_data,
                'severity': self._calculate_severity(anomaly_percentage, anomaly_scores),
                'recommendations': self._get_recommendations(features_df, predictions)
            }
            
            logger.info(f"Anomaly detection completed: {result['status']}")
            return result
            
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _calculate_severity(self, anomaly_percentage: float, scores: np.ndarray) -> str:
        """Calculate severity level based on anomaly percentage and scores"""
        min_score = np.min(scores)
        
        if anomaly_percentage > 20 or min_score < -0.5:
            return 'critical'
        elif anomaly_percentage > 10 or min_score < -0.3:
            return 'high'
        elif anomaly_percentage > 5 or min_score < -0.1:
            return 'medium'
        else:
            return 'low'
    
    def _get_recommendations(self, features_df: pd.DataFrame, predictions: np.ndarray) -> List[str]:
        """Get recommendations based on detected anomalies"""
        recommendations = []
        
        if np.any(predictions == -1):
            anomalous_data = features_df[predictions == -1]
            
            if 'cpu_usage' in features_df.columns and anomalous_data['cpu_usage'].mean() > 80:
                recommendations.append("High CPU usage detected. Consider scaling up or optimizing processes.")
            
            if 'memory_usage' in features_df.columns and anomalous_data['memory_usage'].mean() > 80:
                recommendations.append("High memory usage detected. Check for memory leaks or increase memory allocation.")
            
            if 'error_rate' in features_df.columns and anomalous_data['error_rate'].mean() > 10:
                recommendations.append("High error rate detected. Review application logs and fix critical issues.")
            
            if 'response_time' in features_df.columns and anomalous_data['response_time'].mean() > 2.0:
                recommendations.append("Slow response times detected. Optimize database queries and API calls.")
        
        if not recommendations:
            recommendations.append("System appears to be operating normally.")
        
        return recommendations

def main():
    """Main function to run anomaly detection"""
    detector = AnomalyDetector()
    
    # Train the model
    logger.info("Training anomaly detection model...")
    if not detector.train_model():
        logger.error("Failed to train model")
        return
    
    # Fetch current metrics
    logger.info("Fetching current metrics...")
    current_metrics = detector.fetch_metrics_data()
    
    # Detect anomalies
    logger.info("Running anomaly detection...")
    results = detector.detect_anomalies(current_metrics)
    
    # Print results
    print(json.dumps(results, indent=2))
    
    # Return results for external use
    return results

if __name__ == "__main__":
    main()
