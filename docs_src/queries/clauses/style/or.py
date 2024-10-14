import edgy

# Create some records

await User.query.create(name="Adam", email="adam@edgy.dev")
await User.query.create(name="Eve", email="eve@edgy.dev")

# Query using the global or_ with multiple ANDed field queries
await User.query.or_(name="Adam", email="adam@edgy.dev")
