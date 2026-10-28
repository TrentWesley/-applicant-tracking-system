from candidates.models import Candidate, Source


def make_candidate(email="ann.lee@example.com", **extra):
    fields = {"first_name": "Ann", "last_name": "Lee", "source": Source.REFERRAL} | extra
    return Candidate.objects.create(email=email, **fields)
