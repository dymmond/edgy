# Create some fake data
blue_team = await Team.query.create(name="Blue Team")
green_team = await Team.query.create(name="Green Team")

# Add the teams to the organisation
organisation = await Organisation.query.create(ident="Acme Ltd")
organisation.teams.add(blue_team)
organisation.teams.add(green_team)

# Query
blue_team.organisation_teams.filter(name=blue_team.name)
