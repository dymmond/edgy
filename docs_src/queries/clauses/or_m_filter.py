import edgy

# Create some records

await User.query.create(name="Adam", email="adam@edgy.dev")
await User.query.create(name="Eve", email="eve@edgy.dev")

# Query using the or_
await User.query.filter(edgy.or_(User.columns.name == "Adam")).filter(
    edgy.or_(User.columns.email == "adam@edgy.dev")
)
