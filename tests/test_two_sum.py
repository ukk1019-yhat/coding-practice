from problems.two_sum import two_sum


class TestTwoSum:
    def test_example_1(self):
        assert two_sum([2, 7, 11, 15], 9) == [0, 1]

    def test_example_2(self):
        assert two_sum([3, 2, 4], 6) == [1, 2]

    def test_example_3(self):
        assert two_sum([3, 3], 6) == [0, 1]

    def test_no_solution(self):
        assert two_sum([1, 2, 3], 10) == []
