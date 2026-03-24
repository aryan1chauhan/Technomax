import pandas as pd
import joblib
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

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
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        class_weight='balanced',
        max_depth=10,
        min_samples_leaf=2
    )

    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    print("\nTest Set Metrics:")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(f"Precision: {precision_score(y_test, y_pred, zero_division=0):.4f}")
    print(f"Recall: {recall_score(y_test, y_pred, zero_division=0):.4f}")
    print(f"F1 Score: {f1_score(y_test, y_pred, zero_division=0):.4f}")
    
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
