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
            return [], "No assessment marks entered yet. Enter marks in Padikkunnundo to activate subject recommendations."
        
        # Filter valid records with positive max_score
        valid_marks = [m for m in marks_data if m.get('max_score', 0) > 0 and m.get('score') is not None]
        if not valid_marks:
            return [], "No assessment marks entered yet. Enter marks in Padikkunnundo to activate subject recommendations."

        df = pd.DataFrame(valid_marks)
        df['score_pct'] = ((df['score'] / df['max_score']) * 100).clip(lower=0.0, upper=100.0)
        
        overall_avg = float(df['score_pct'].mean())
        
        # Calculate class average per subject
        class_avg = df.groupby('subject')['score_pct'].mean()
        
        # Find weak subjects (< 50% or > 15% below class average)
        weak_subjects = []
        for subject in df['subject'].unique():
            subj_rows = df[df['subject'] == subject]
            student_avg = float(subj_rows['score_pct'].mean())
            class_avg_subj = float(class_avg.get(subject, student_avg))
            gap = class_avg_subj - student_avg
            
            if gap > 12 or student_avg < 50.0:
                weak_subjects.append({
                    'subject': subject,
                    'gap': gap,
                    'student_score': student_avg,
                    'class_avg': class_avg_subj
                })
        
        # Sort by lowest score and highest gap
        weak_subjects.sort(key=lambda x: (x['student_score'], -x['gap']))
        subject_names = [s['subject'] for s in weak_subjects]
        
        if weak_subjects:
            top_weak = weak_subjects[0]
            if top_weak['class_avg'] > top_weak['student_score']:
                recommendation = f"Your {top_weak['subject']} score is {top_weak['student_score']:.0f}% vs class average {top_weak['class_avg']:.0f}%. We recommend dedicating extra review time to this subject before SEA2."
            else:
                recommendation = f"Your {top_weak['subject']} score is {top_weak['student_score']:.0f}%. Additional practice on foundational problem sets will help secure higher marks in SEA2."
        elif overall_avg >= 75.0:
            recommendation = "Great job! Your performance is strong across all enrolled subjects. Maintain regular revision to sustain high mastery."
        else:
            recommendation = "Performance is steady. Consistent weekly practice across all subjects will help push your scores into top percentile."
        
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
        valid_data = [m for m in marks_data_all if m.get('max_score', 0) > 0 and m.get('score') is not None]
        if len(valid_data) < 3:
            return {i: 'Average' for i in range(len(marks_data_all))}
        
        df = pd.DataFrame(valid_data)
        
        # Calculate features for each student
        student_features = []
        student_ids = []
        
        for student_id in df['student_id'].unique():
            student_marks = df[df['student_id'] == student_id].copy()
            
            # Feature 1: Average score percentage (bounded 0-100)
            student_marks['score_pct'] = ((student_marks['score'] / student_marks['max_score']) * 100).clip(lower=0.0, upper=100.0)
            avg_score = float(student_marks['score_pct'].mean())
            
            # Feature 2: Score standard deviation (consistency)
            std_dev = float(student_marks['score_pct'].std() or 0)
            
            # Feature 3: Improvement trend (difference between last and first exam)
            if len(student_marks) > 1:
                improvement = float(student_marks['score_pct'].iloc[-1] - student_marks['score_pct'].iloc[0])
            else:
                improvement = 0.0
            
            student_features.append([avg_score, std_dev, improvement])
            student_ids.append(student_id)
        
        if not student_features or len(student_features) < 3:
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
        cluster_labels = {
            cluster_means[0][0]: 'At-Risk',
            cluster_means[1][0]: 'Average',
            cluster_means[2][0]: 'Topper'
        }
        
        return {student_ids[i]: cluster_labels[clusters[i]] for i in range(len(student_ids))}

class AnomalyDetector:
    """ML Module 3: Anomaly Detection using Z-Score"""
    
    @staticmethod
    def detect_anomalies(student_marks_history, threshold=2.0):
        """
        Algorithm: Z-Score Outlier Detection
        Detects sudden drops or spikes in student performance
        """
        valid_history = [m for m in student_marks_history if m.get('max_score', 0) > 0 and m.get('score') is not None]
        if len(valid_history) < 3:
            return []
        
        df = pd.DataFrame(valid_history)
        df['score_pct'] = ((df['score'] / df['max_score']) * 100).clip(lower=0.0, upper=100.0)
        
        scores = df['score_pct'].values
        mean = np.mean(scores)
        std = np.std(scores)
        
        if std == 0:
            return []
        
        anomalies = []
        for i, row in df.iterrows():
            z_score = (row['score_pct'] - mean) / std
            
            if abs(z_score) > threshold:
                anomaly_type = 'drop' if z_score < 0 else 'spike'
                anomalies.append({
                    'exam_type': row.get('exam_type', 'Unknown'),
                    'subject': row['subject'],
                    'score': row['score'],
                    'score_pct': row['score_pct'],
                    'z_score': z_score,
                    'type': anomaly_type,
                    'message': f"Significant performance {anomaly_type} in {row['subject']}: {row['score_pct']:.1f}% (Z-Score: {z_score:.2f})"
                })
        
        return sorted(anomalies, key=lambda x: x['z_score'])


class ExamDifficultyAnalyzer:
    """
    ML Module 4: Exam Difficulty & Class Context Analyzer
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
        valid_all = [m for m in (all_marks_data or []) if m.get('max_score', 0) > 0 and m.get('score') is not None]
        valid_stu = [m for m in (student_marks_data or []) if m.get('max_score', 0) > 0 and m.get('score') is not None]

        if not valid_all:
            return {
                'difficulty': 'Pending Data',
                'difficulty_level': 'moderate',
                'class_avg_pct': None,
                'student_avg_pct': None,
                'high_score_ratio': 0,
                'interpretation': 'No marks entered yet for this assessment. Enter marks in Padikkunnundo to calculate class performance benchmarks.'
            }

        df_all = pd.DataFrame(valid_all)
        if selected_subject:
            df_all = df_all[df_all['subject'].str.lower() == selected_subject.lower()]

        if df_all.empty:
            return {
                'difficulty': 'Pending Data',
                'difficulty_level': 'moderate',
                'class_avg_pct': None,
                'student_avg_pct': None,
                'high_score_ratio': 0,
                'interpretation': f'No marks entered yet for {selected_subject or "this assessment"}. Enter marks in Padikkunnundo to calculate benchmarks.'
            }

        df_all['score_pct'] = ((df_all['score'] / df_all['max_score']) * 100).clip(lower=0.0, upper=100.0)
        class_avg_pct = float(df_all['score_pct'].mean())
        
        # Ratio of students scoring >= 80% (equivalent to >8 out of 10)
        high_scorers = len(df_all[df_all['score_pct'] >= 80.0])
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

        if valid_stu:
            df_stu = pd.DataFrame(valid_stu)
            if selected_subject:
                df_stu = df_stu[df_stu['subject'].str.lower() == selected_subject.lower()]
            
            if not df_stu.empty:
                df_stu['score_pct'] = ((df_stu['score'] / df_stu['max_score']) * 100).clip(lower=0.0, upper=100.0)
                student_avg_pct = float(df_stu['score_pct'].mean())

                if (high_score_ratio >= 0.35 or class_avg_pct >= 70.0) and student_avg_pct <= 40.0:
                    interpretation = (
                        f"The class scored an average of {class_avg_pct:.0f}% in this assessment. "
                        f"Your score was {student_avg_pct:.0f}%. Focus on the core foundational topics before your next assessment—"
                        f"with regular problem solving, you can quickly bridge the gap!"
                    )
                elif difficulty_level == "hard" and student_avg_pct <= 45.0:
                    interpretation = (
                        f"This assessment was challenging across the class (Class Avg: {class_avg_pct:.0f}%). "
                        f"Your score of {student_avg_pct:.0f}% reflects the difficulty level of the paper. "
                        f"Stay focused and practice previous question papers to build confidence."
                    )
                elif student_avg_pct >= 80.0:
                    interpretation = (
                        f"Outstanding performance! You scored {student_avg_pct:.0f}% "
                        f"(Class Avg: {class_avg_pct:.0f}%). Keep up the great work and maintain this momentum!"
                    )
                elif student_avg_pct >= class_avg_pct:
                    interpretation = (
                        f"Well done! You are performing above the class average ({student_avg_pct:.0f}% vs {class_avg_pct:.0f}%). "
                        f"Keep practicing regularly to secure top grades."
                    )
                else:
                    interpretation = (
                        f"Your score of {student_avg_pct:.0f}% is near the class average ({class_avg_pct:.0f}%). "
                        f"A little dedicated revision before the next assessment will help you push into the top tier."
                    )

        if not interpretation:
            if not valid_stu:
                interpretation = f"Class average is {class_avg_pct:.0f}%. Enter your marks in Padikkunnundo to compare your performance and get tailored guidance."
            else:
                interpretation = f"Overall class average is {class_avg_pct:.0f}%, indicating a {difficulty.lower()} assessment level."

        return {
            'difficulty': difficulty,
            'difficulty_level': difficulty_level,
            'class_avg_pct': round(class_avg_pct, 1),
            'student_avg_pct': round(student_avg_pct, 1) if student_avg_pct is not None else None,
            'high_score_ratio': round(high_score_ratio, 2),
            'interpretation': interpretation
        }
