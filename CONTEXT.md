# LinkGuard

LinkGuard tells a user how risky a pasted link is, why, and what to do next. Its model is trained on the PhiUSIIL phishing URL dataset.

## Language

**Feature set**:
The saved file holding the ten hostname features, the label and the cleaned host for every row of the cleaned dataset. It is the only input the model trains on.
_Avoid_: feature file, training features, feature matrix

**Training split**:
The rows of the feature set that the saved split marks `train`. Rows are split by host, so no host has rows in both the training and the test split.
_Avoid_: training set, train data, training part
