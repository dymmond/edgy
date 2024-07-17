import edgy

# Create some records

await User.query.create(name="Adam", email="adam@edgy.dev")
await User.query.create(name="Eve", email="eve@edgy.dev")

# Query using the and_
await User.query.filter(edgy.and_(User.columns.name == "Adam")).filter(
    edgy.and_(User.columns.email == "adam@edgy.dev")
)
