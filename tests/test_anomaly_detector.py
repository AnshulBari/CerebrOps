"""
Test suite for CerebrOps anomaly detection module
"""

import unittest
from unittest.mock import Mock, patch
import numpy as np
from anomaly_detector import AnomalyDetector

class TestAnomalyDetector(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.detector = AnomalyDetector(contamination=0.1)
    
    def test_detector_initialization(self):
        """Test detector initialization"""
        self.assertEqual(self.detector.contamination, 0.1)
        self.assertFalse(self.detector.is_trained)
    
    def test_generate_sample_data(self):
        """Test sample data generation"""
        data = self.detector._generate_sample_data()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        
        # Check if required fields exist
        first_item = data[0]
        required_fields = ['timestamp', 'cpu_usage', 'memory_usage', 'disk_usage']
        for field in required_fields:
            self.assertIn(field, first_item)
    
    def test_prepare_features(self):
        """Test feature preparation"""
        sample_data = self.detector._generate_sample_data()
        features_df = self.detector.prepare_features(sample_data)
        
        self.assertFalse(features_df.empty)
        self.assertGreater(len(features_df.columns), 0)
    
    def test_model_training(self):
        """Test model training"""
        training_data = self.detector._generate_sample_data()
        result = self.detector.train_model(training_data)
        
        self.assertTrue(result)
        self.assertTrue(self.detector.is_trained)
    
    def test_anomaly_detection_without_training(self):
        """Test anomaly detection when model is not trained"""
        test_data = self.detector._generate_sample_data()[:10]
        result = self.detector.detect_anomalies(test_data)
        
        self.assertIn('status', result)
        # Should automatically train and then detect
        self.assertTrue(self.detector.is_trained)
    
    def test_anomaly_detection_with_training(self):
        """Test anomaly detection with pre-trained model"""
        # Train the model first
        training_data = self.detector._generate_sample_data()
        self.detector.train_model(training_data)
        
        # Test with normal data
        test_data = training_data[:10]
        result = self.detector.detect_anomalies(test_data)
        
        self.assertIn('status', result)
        self.assertIn('timestamp', result)
        self.assertIn('total_data_points', result)
        self.assertIn('anomaly_count', result)
    
    def test_severity_calculation(self):
        """Test severity calculation"""
        scores = np.array([-0.1, -0.2, -0.3, -0.6])
        
        severity = self.detector._calculate_severity(5.0, scores)
        self.assertIn(severity, ['low', 'medium', 'high', 'critical'])
        
        severity = self.detector._calculate_severity(25.0, scores)
        self.assertEqual(severity, 'critical')
    
    def test_recommendations_generation(self):
        """Test recommendations generation"""
        import pandas as pd
        
        # Create test data with high values
        test_df = pd.DataFrame({
            'cpu_usage': [90, 95, 85],
            'memory_usage': [85, 90, 80],
            'error_rate': [15, 20, 12]
        })
        predictions = np.array([-1, -1, -1])  # All anomalies
        
        recommendations = self.detector._get_recommendations(test_df, predictions)
        
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
    
    @patch('requests.get')
    def test_fetch_metrics_data_success(self, mock_get):
        """Test successful metrics fetching"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'cpu_usage': 50,
            'memory_usage': 60,
            'timestamp': '2023-01-01T00:00:00'
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        data = self.detector.fetch_metrics_data()
        
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
    
    @patch('requests.get')
    def test_fetch_metrics_data_failure(self, mock_get):
        """Test metrics fetching failure"""
        mock_get.side_effect = Exception("Connection error")
        
        data = self.detector.fetch_metrics_data()
        
        # Should return sample data on failure
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

if __name__ == '__main__':
    unittest.main()
