# This assumes you have the models imported
# or accessible from somewhere allowing you to generate
# these records in your database


acme = await Organisation.query.create(ident="ACME Ltd")
red_team = await Team.query.create(org=acme, name="Red Team")
blue_team = await Team.query.create(org=acme, name="Blue Team")

await Member.query.create(team=red_team, email="charlie@redteam.com")
await Member.query.create(team=red_team, email="brown@redteam.com")
await Member.query.create(team=blue_team, email="monica@blueteam.com")
await Member.query.create(team=blue_team, email="snoopy@blueteam.com")
