import edgy

# Create some records

await User.query.create(name="Adam", email="adam@edgy.dev")
await User.query.create(name="Eve", email="eve@edgy.dev")
await User.query.create(name="John", email="john@example.com")

# Query using the not_
await User.query.filter(email__icontains="edgy").not_(name__iexact="Adam")
