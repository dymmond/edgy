# Create some records

await User.query.create(name="Adam", email="adam@edgy.dev")
await User.query.create(name="Eve", email="eve@edgy.dev")

# Query using the multiple or_
await User.query.or_({"email__icontains": "edgy"}, {"name__icontains": "a"})

# QUery using the global or
await User.query.or_(email__icontains="edgy").or_(name__icontains="a")

# Query using the or_ with multiple ANDed field queries
await User.query.or_(email__icontains="edgy", name__icontains="a")
