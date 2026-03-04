import torch
import torch.nn as nn

# Define vocabulary: lowercase a-z, space, hyphen, and common accented chars
VOCAB_STRING = "abcdefghijklmnopqrstuvwxyz -'àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ"
CHAR_TO_IDX = {char: idx + 1 for idx, char in enumerate(VOCAB_STRING)}
VOCAB_SIZE = len(CHAR_TO_IDX) + 1 # +1 for padding index 0
MAX_LEN = 20

def string_to_tensor(s):
    """Convert string to a padded/truncated tensor of character indices."""
    if not isinstance(s, str):
        s = str(s)
    s = s.lower()
    indices = [CHAR_TO_IDX.get(c, 0) for c in s] # 0 used for unknown chars as well as padding
    
    # Trim or pad
    if len(indices) > MAX_LEN:
        indices = indices[:MAX_LEN]
    else:
        indices = indices + [0] * (MAX_LEN - len(indices))
        
    return torch.tensor(indices, dtype=torch.long)

class SiameseBiLSTM(nn.Module):
    def __init__(self, vocab_size=VOCAB_SIZE, embedding_dim=64, hidden_dim=64, num_layers=2):
        super(SiameseBiLSTM, self).__init__()
        
        # Embedding layer mapping char indices to dense vectors
        self.embedding = nn.Embedding(num_embeddings=vocab_size, embedding_dim=embedding_dim, padding_idx=0)
        
        # Bi-directional LSTM
        self.lstm = nn.LSTM(
            input_size=embedding_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            bidirectional=True,
            batch_first=True
        )
        
        # Fully connected layer bringing the concat state back to 64-dim representation
        self.fc = nn.Linear(hidden_dim * 2, 64)
        
    def forward_once(self, x):
        # x shape: (batch_size, seq_len)
        embedded = self.embedding(x) # (batch_size, seq_len, embedding_dim)
        
        # Forward pass through LSTM
        # h_n shape: (num_layers * num_directions, batch_size, hidden_size)
        _, (h_n, _) = self.lstm(embedded)
        
        # Extract the final hidden state of the last layer for both directions
        # h_n[-2, :, :] -> forward direction of last layer
        # h_n[-1, :, :] -> backward direction of last layer
        final_forward = h_n[-2, :, :]
        final_backward = h_n[-1, :, :]
        
        # Concatenate forward and backward hidden states
        concat = torch.cat((final_forward, final_backward), dim=1) # (batch_size, hidden_dim * 2)
        
        # Map to final dense vector
        out = self.fc(concat) # (batch_size, 64)
        
        return out

    def forward(self, x1, x2):
        # Pass both inputs through the shared network weights geometrically
        out1 = self.forward_once(x1)
        out2 = self.forward_once(x2)
        return out1, out2
