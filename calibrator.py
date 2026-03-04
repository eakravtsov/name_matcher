import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader
from sklearn.linear_model import LogisticRegression
import joblib
import pandas as pd
from tqdm import tqdm
from siamese_model import SiameseBiLSTM
from train import NamePairsDataset

def train_calibrator():
    print("Loading validation dataset...")
    val_dataset = NamePairsDataset('val.csv')
    val_loader = DataLoader(val_dataset, batch_size=256, shuffle=False)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    # Load architecture and weights
    model = SiameseBiLSTM().to(device)
    model.load_state_dict(torch.load('best_siamese_model.pt', map_location=device, weights_only=True))
    model.eval()
    
    distances = []
    labels_list = []
    
    print("Extracting Euclidean representations from validation set...")
    with torch.no_grad():
        for t1, t2, labels in tqdm(val_loader, desc="Level 2 Extraction"):
            t1, t2 = t1.to(device), t2.to(device)
            out1, out2 = model(t1, t2)
            dist = F.pairwise_distance(out1, out2).cpu().numpy()
            distances.extend(dist)
            labels_list.extend(labels.numpy())
            
    # Reshape distances into singular feature array for Sklearn
    X = [[float(d)] for d in distances]
    y = [float(lbl) for lbl in labels_list]
    
    print("Fitting Logistic Regression for Platt Scaling...")
    lr = LogisticRegression(class_weight='balanced')
    lr.fit(X, y)
    
    print(f"Calibration successful.")
    print("Sample Output Geometry:")
    for dist_val in [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]:
        prob = lr.predict_proba([[dist_val]])[0][1]
        print(f"  Euclidean Dist {dist_val:.1f}  ->  {prob*100:6.1f}% Confidence Match")
        
    joblib.dump(lr, 'calibrator.pkl')
    print("Saved calibrator weights to calibrator.pkl")

if __name__ == "__main__":
    train_calibrator()
