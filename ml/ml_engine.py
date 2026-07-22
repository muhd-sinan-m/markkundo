import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import json

class StudyFocusRecommender:
    """ML Module 1: Study Focus Recommender"""
    
    @staticmethod
    def analyze(marks_data):
        """
        Algorithm: Weighted subject scoring + threshold comparison
        Returns list of weak subjects ranked by severity
        """
        if not marks_data:
            return [], "No data available"
        
        df = pd.DataFrame(marks_data)
        
        # Calculate student score percentage per subject
        df['score_pct'] = (df['score'] / df['max_score']) * 100
        
        # Calculate class average per subject
        class_avg = df.groupby('subject')['score_pct'].mean()
        
        # Find weak subjects (>15% below class average)
        weak_subjects = []
        for subject in df['subject'].unique():
            student_avg = df[df['subject'] == subject]['score_pct'].mean()
            class_avg_subj = class_avg.get(subject, 0)
            gap = class_avg_subj - student_avg
            
            if gap > 15:
                weak_subjects.append({
                    'subject': subject,
                    'gap': gap,
                    'student_score': student_avg,
                    'class_avg': class_avg_subj
                })
        
        # Sort by severity
        weak_subjects.sort(key=lambda x: x['gap'], reverse=True)
        subject_names = [s['subject'] for s in weak_subjects]
        
        if weak_subjects:
            top_weak = weak_subjects[0]
            recommendation = f"Your {top_weak['subject']} score is {top_weak['student_score']:.0f}% vs class average {top_weak['class_avg']:.0f}%. We recommend focusing on this subject before your next assessment."
        else:
            recommendation = "Great job! Your performance is above class average across all subjects. Keep up the momentum!"
        
        return subject_names, recommendation

class PerformanceClusterer:
    """ML Module 2: Performance Clustering using K-Means"""
    
    @staticmethod
    def cluster_students(marks_data_all):
        """
        Algorithm: K-Means Clustering (k=3)
        Features: average score %, score standard deviation, improvement trend
        Returns: cluster assignments (Topper, Average, At-Risk)
        """
        if len(marks_data_all) < 3:
            # Not enough data for clustering
            return {i: 'Average' for i in range(len(marks_data_all))}
        
        df = pd.DataFrame(marks_data_all)
        
        # Calculate features for each student
        student_features = []
        student_ids = []
        
        for student_id in df['student_id'].unique():
            student_marks = df[df['student_id'] == student_id]
            
            # Feature 1: Average score percentage
            student_marks['score_pct'] = (student_marks['score'] / student_marks['max_score']) * 100
            avg_score = student_marks['score_pct'].mean()
            
            # Feature 2: Score standard deviation (consistency)
            std_dev = student_marks['score_pct'].std() or 0
            
            # Feature 3: Improvement trend (difference between last and first exam)
            if len(student_marks) > 1:
                improvement = student_marks['score_pct'].iloc[-1] - student_marks['score_pct'].iloc[0]
            else:
                improvement = 0
            
            student_features.append([avg_score, std_dev, improvement])
            student_ids.append(student_id)
        
        if not student_features:
            return {}
        
        # Normalize features
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(student_features)
        
        # K-Means clustering with k=3
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(features_scaled)
        
        # Map clusters to labels: 0=At-Risk, 1=Average, 2=Topper (based on avg score)
        cluster_means = []
        for i in range(3):
            cluster_avg = np.mean([f[0] for f, c in zip(student_features, clusters) if c == i])
            cluster_means.append((i, cluster_avg))
        
        cluster_means.sort(key=lambda x: x[1])
        cluster_map = {
            cluster_means[0][0]: 'At-Risk',
            cluster_means[1][0]: 'Average',
            cluster_means[2][0]: 'Topper'
        }
        
        result = {}
        for student_id, cluster in zip(student_ids, clusters):
            result[student_id] = cluster_map[cluster]
        
        return result

class AnomalyDetector:
    """ML Module 3: Anomaly Detector using Z-Score"""
    
    @staticmethod
    def detect_anomalies(marks_data):
        """
        Algorithm: Z-Score statistical anomaly detection
        Z-score < -2.0: critical anomaly
        Z-score -1.5 to -2.0: warning anomaly
        """
        if len(marks_data) < 2:
            return []
        
        df = pd.DataFrame(marks_data)
        anomalies = []
        
        for subject in df['subject'].unique():
            subject_data = df[df['subject'] == subject]
            scores = subject_data['score'].values
            
            if len(scores) < 2:
                continue
            
            # Calculate z-scores
            mean_score = np.mean(scores)
            std_score = np.std(scores)
            
            if std_score == 0:
                continue
            
            z_score = (scores[-1] - mean_score) / std_score
            
            if z_score < -2.0:
                anomalies.append({
                    'subject': subject,
                    'risk_level': 'critical',
                    'z_score': z_score,
                    'message': f"Significant drop in {subject} marks detected. You're performing notably below your average. Consider reaching out to faculty for support."
                })
            elif z_score < -1.5:
                anomalies.append({
                    'subject': subject,
                    'risk_level': 'warning',
                    'z_score': z_score,
                    'message': f"Notable drop in {subject} marks compared to your previous performance. Consider reviewing the concepts."
                })
        
        return sorted(anomalies, key=lambda x: x['z_score'])
