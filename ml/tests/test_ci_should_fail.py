# Deliberately failing test, to prove the ml job turns red and names the
# failing file and test. Reverted before review.
def test_deliberately_fails():
    assert 1 + 1 == 3
