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


class ExamDifficultyAnalyzer:
    """
    ML Module 4: Exam Difficulty & Cohort Context Analyzer
    Evaluates paper difficulty based on total class performance distribution,
    and provides empathetic, calm, and constructive feedback.
    """
    @staticmethod
    def analyze_difficulty(all_marks_data, student_marks_data=None, selected_subject=None):
        """
        - all_marks_data: list of marks dicts for the exam across all students
        - student_marks_data: list of marks dicts for the specific student
        - selected_subject: optional subject filter
        """
        if not all_marks_data:
            return {
                'difficulty': 'Moderate',
                'difficulty_level': 'moderate',
                'class_avg_pct': 0,
                'high_score_ratio': 0,
                'interpretation': 'Standard assessment difficulty.'
            }

        df_all = pd.DataFrame(all_marks_data)
        if selected_subject:
            df_all = df_all[df_all['subject'] == selected_subject]

        if df_all.empty:
            return {
                'difficulty': 'Moderate',
                'difficulty_level': 'moderate',
                'class_avg_pct': 0,
                'high_score_ratio': 0,
                'interpretation': 'Standard assessment difficulty.'
            }

        df_all['score_pct'] = (df_all['score'] / df_all['max_score']) * 100
        class_avg_pct = float(df_all['score_pct'].mean())
        
        # Ratio of students scoring >= 80% (equivalent to >8 out of 10)
        high_scorers = len(df_all[df_all['score_pct'] >= 80])
        high_score_ratio = (high_scorers / len(df_all)) if len(df_all) > 0 else 0

        # Classify difficulty based on overall class average
        if class_avg_pct < 50.0:
            difficulty = "Challenging"
            difficulty_level = "hard"
        elif class_avg_pct <= 75.0:
            difficulty = "Moderate"
            difficulty_level = "moderate"
        else:
            difficulty = "Accessible"
            difficulty_level = "easy"

        # Personalized interpretation & encouraging feedback
        student_avg_pct = None
        interpretation = ""

        if student_marks_data:
            df_stu = pd.DataFrame(student_marks_data)
            if selected_subject:
                df_stu = df_stu[df_stu['subject'] == selected_subject]
            
            if not df_stu.empty:
                df_stu['score_pct'] = (df_stu['score'] / df_stu['max_score']) * 100
                student_avg_pct = float(df_stu['score_pct'].mean())

                # Special scenario:
                # Many students scored >80% (>8/10), but student scored <=35% (e.g., 3/10)
                if (high_score_ratio >= 0.35 or class_avg_pct >= 70.0) and student_avg_pct <= 40.0:
                    interpretation = (
                        f"The class performed strongly in this assessment (Class Avg: {class_avg_pct:.0f}%, with many students scoring above 80%). "
                        f"Your score was {student_avg_pct:.0f}%. While this shows a gap in preparation for this specific test, "
                        f"take a deep breath—everyone encounters setbacks from time to time! Don't be discouraged at all. "
                        f"With calm, focused practice on the core concepts and revising previous papers, you can easily turn this around and excel in the next assessment. "
                        f"We believe in your potential!"
                    )
                elif difficulty_level == "hard" and student_avg_pct <= 45.0:
                    interpretation = (
                        f"This assessment was particularly tough across the entire cohort (Class Avg: {class_avg_pct:.0f}%). "
                        f"Your score of {student_avg_pct:.0f}% reflects the high difficulty level of the paper. "
                        f"Stay positive, practice key problem types, and you will see strong progress."
                    )
                elif student_avg_pct >= 80.0:
                    interpretation = (
                        f"Outstanding achievement! You scored an impressive {student_avg_pct:.0f}% "
                        f"(Class Avg: {class_avg_pct:.0f}%). Keep up the great work and maintain this momentum!"
                    )
                elif student_avg_pct >= class_avg_pct:
                    interpretation = (
                        f"Well done! You are performing comfortably above the class average ({student_avg_pct:.0f}% vs {class_avg_pct:.0f}%). "
                        f"Keep practicing regularly to secure high grades."
                    )
                else:
                    interpretation = (
                        f"Your score of {student_avg_pct:.0f}% is close to the class average ({class_avg_pct:.0f}%). "
                        f"A little dedicated review before the next test will help you push into the top tier."
                    )

        if not interpretation:
            interpretation = f"Overall class average is {class_avg_pct:.0f}%, indicating a {difficulty.lower()} assessment level."

        return {
            'difficulty': difficulty,
            'difficulty_level': difficulty_level,
            'class_avg_pct': round(class_avg_pct, 1),
            'student_avg_pct': round(student_avg_pct, 1) if student_avg_pct is not None else None,
            'high_score_ratio': round(high_score_ratio, 2),
            'interpretation': interpretation
        }

