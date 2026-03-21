import pandas as pd
import joblib
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

def train():
    data_path = os.path.join(os.path.dirname(__file__), 'training_data.csv')
    
    # 2. If file not found or empty: print error and exit
    if not os.path.exists(data_path):
        print("Error: training_data.csv not found.")
        return
        
    df = pd.read_csv(data_path)
    
    if df.empty:
        print("Error: training_data.csv is empty.")
        return
        
    # 3. Features (X) = all columns except 'was_selected'
    # 4. Target (y) = 'was_selected'
    X = df.drop(columns=['was_selected'])
    y = df['was_selected']
    
    # 5. Check class balance
    print("Class Balance:")
    print(y.value_counts().to_string())
    
    # 6. Split 80/20 train/test with random_state=42
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 7. Train RandomForestClassifier
    model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
    model.fit(X_train, y_train)
    
    # 8. Print on test set Metrics
    y_pred = model.predict(X_test)
    print("\nTest Set Metrics:")
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(f"Precision: {precision_score(y_test, y_pred, zero_division=0):.4f}")
    print(f"Recall: {recall_score(y_test, y_pred, zero_division=0):.4f}")
    print(f"F1 Score: {f1_score(y_test, y_pred, zero_division=0):.4f}")
    
    # 9. Print feature importances ranked highest to lowest
    print("\nFeature Importances:")
    importances = model.feature_importances_
    feature_importances = sorted(zip(X.columns, importances), key=lambda x: x[1], reverse=True)
    for feature, imp in feature_importances:
        print(f"{feature}: {imp:.6f}")
        
    # 10. Save model
    model_path = os.path.join(os.path.dirname(__file__), 'hospital_model.pkl')
    joblib.dump(model, model_path)
    
    # 11. Print summary
    print("Model saved to hospital_model.pkl")

if __name__ == '__main__':
    train()
