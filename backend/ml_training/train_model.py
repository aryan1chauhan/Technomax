import pandas as pd
import joblib
import os
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, precision_recall_curve

def train():
    data_path = os.path.join(os.path.dirname(__file__), 'training_data.csv')
    
    if not os.path.exists(data_path):
        print("Error: training_data.csv not found.")
        return
        
    df = pd.read_csv(data_path)
    
    if df.empty:
        print("Error: training_data.csv is empty.")
        return
        
    X = df.drop(columns=['was_selected'])
    y = df['was_selected']
    
    print("Class Balance:")
    print(y.value_counts().to_string())
    
    # Calculate scale_pos_weight from actual class ratio
    neg_count = (y == 0).sum()
    pos_count = (y == 1).sum()
    auto_weight = neg_count / pos_count if pos_count > 0 else 1
    print(f"\nAuto scale_pos_weight: {auto_weight:.1f} ({neg_count} neg / {pos_count} pos)")
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.1,
        scale_pos_weight=auto_weight,
        min_child_weight=3,
        eval_metric='logloss',
        random_state=42
    )
    model.fit(X_train, y_train)
    
    # Test set metrics
    y_pred = model.predict(X_test)
    print("\nTest Set Metrics:")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(f"Precision: {precision_score(y_test, y_pred, zero_division=0):.4f}")
    print(f"Recall: {recall_score(y_test, y_pred, zero_division=0):.4f}")
    print(f"F1 Score: {f1_score(y_test, y_pred, zero_division=0):.4f}")
    
    # Optimal threshold tuning
    y_proba = model.predict_proba(X_test)[:, 1]
    precisions, recalls, thresholds = precision_recall_curve(y_test, y_proba)
    f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-8)
    best_threshold = thresholds[np.argmax(f1_scores)]
    print(f"\nOptimal threshold: {best_threshold:.4f}")

    y_pred_tuned = (y_proba >= best_threshold).astype(int)
    print(f"Tuned Precision: {precision_score(y_test, y_pred_tuned, zero_division=0):.4f}")
    print(f"Tuned Recall: {recall_score(y_test, y_pred_tuned, zero_division=0):.4f}")
    print(f"Tuned F1: {f1_score(y_test, y_pred_tuned, zero_division=0):.4f}")
    
    # Cross-validation
    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='f1')
    print(f"\nCross-val F1: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")
    
    # Feature importances
    print("\nFeature Importances:")
    importances = model.feature_importances_
    feature_importances = sorted(zip(X.columns, importances), key=lambda x: x[1], reverse=True)
    for feature, imp in feature_importances:
        print(f"{feature}: {imp:.6f}")
        
    # Save model
    model_path = os.path.join(os.path.dirname(__file__), 'hospital_model.pkl')
    joblib.dump(model, model_path)
    
    print("\nModel saved to hospital_model.pkl")

if __name__ == '__main__':
    train()

