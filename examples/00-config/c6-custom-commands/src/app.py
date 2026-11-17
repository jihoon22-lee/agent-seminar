"""리뷰 연습용 작은 파일 (/review src/app.py 로 불러 본다)."""


def average(numbers):
    return sum(numbers) / len(numbers)


def top_two(scores):
    scores.sort(reverse=True)
    return scores[0], scores[1]
