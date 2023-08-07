# Create some fake data
blue_team = await Team.query.create(name="Blue Team")
green_team = await Team.query.create(name="Green Team")

# Add the teams to the organisation
organisation = await Organisation.query.create(ident="Acme Ltd")
await organisation.teams.add(blue_team)
await organisation.teams.add(green_team)

# Query
await blue_team.team_organisationteams_set.filter(name=blue_team.name)
