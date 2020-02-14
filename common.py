import hashlib

def get_hash(string, length):
    h = hashlib.sha256()
    h.update(bytes(string, "utf-8"))
    response_hash = h.hexdigest()[:length]
    return response_hash


def get_packages_hash(packages):
    return get_hash(" ".join(sorted(list(set(packages)))), 12)

