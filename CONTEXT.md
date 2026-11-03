# LinkGuard

LinkGuard tells a user how risky a pasted link is, why, and what to do next. Its model is trained on the PhiUSIIL phishing URL dataset.

## Language

**Feature set**:
The ten hostname features and the label for every row of the cleaned dataset. It is the only input the model trains on.
_Avoid_: feature file, training features, feature matrix

**Training split**:
The feature set's rows kept for training. Rows are split by host, so no host has rows in both the training and the test split.
_Avoid_: training set, train data, training part
