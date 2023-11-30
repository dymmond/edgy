# Create some records

await User.query.create(name="Adam", email="adam@edgy.dev")
await User.query.create(name="Eve", email="eve@edgy.dev")

# Query using the or_
await User.query.or_(name="Adam").filter(email="adam@edgy.dev")
