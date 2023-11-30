import edgy

# Create some records

await User.query.create(name="Adam", email="adam@edgy.dev")
await User.query.create(name="Eve", email="eve@edgy.dev")

# Query using the not_
await User.query.filter(edgy.not_(User.columns.name == "Adam"))
