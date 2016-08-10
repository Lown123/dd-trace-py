
# stdlib
import time

# 3p
from nose.tools import eq_
from pymongo import MongoClient

# project
from ddtrace.contrib.pymongo.trace import trace_mongo_client, normalize_filter
from ddtrace import Tracer


from ...test_tracer import DummyWriter


def test_normalize_filter():
    # ensure we can properly normalize queries FIXME[matt] move to the agent
    cases = [
        (None, {}),
        (
            {"team":"leafs"},
            {"team": "?"},
        ),
        (
            {"age": {"$gt" : 20}},
            {"age": {"$gt" : "?"}},
        ),
        (
            {
                "status": "A",
                "$or": [ { "age": { "$lt": 30 } }, { "type": 1 } ]
            },
            {
                "status": "?",
                "$or": [ { "age": { "$lt": "?" } }, { "type": "?" } ]
            }
        )
    ]
    for i, expected in cases:
        out = normalize_filter(i)
        eq_(expected, out)


def test_update():
    # ensure we trace deletes
    tracer, client = _get_tracer_and_client("songdb")
    writer = tracer.writer
    db = client["testdb"]
    db.drop_collection("songs")
    input_songs = [
        {'name' : 'Powderfinger', 'artist':'Neil'},
        {'name' : 'Harvest', 'artist':'Neil'},
        {'name' : 'Suzanne', 'artist':'Leonard'},
        {'name' : 'Partisan', 'artist':'Leonard'},
    ]
    db.songs.insert_many(input_songs)

    result = db.songs.update_many(
        {"artist":"Neil"},
        {"$set": {"artist":"Shakey"}},
    )

    eq_(result.matched_count, 2)
    eq_(result.modified_count, 2)

    # ensure all is traced.
    spans = writer.pop()
    assert spans, spans
    for span in spans:
        # ensure all the of the common metadata is set
        eq_(span.service, "songdb")
        eq_(span.span_type, "mongodb")
        eq_(span.meta.get("mongodb.collection"), "songs")
        eq_(span.meta.get("mongodb.db"), "testdb")
        assert span.meta.get("out.host")
        assert span.meta.get("out.port")

    expected_resources = set([
        "drop songs",
        'update songs {"artist": "?"}',
        "insert songs",
    ])

    eq_(expected_resources, {s.resource for s in spans})


def test_delete():
    # ensure we trace deletes
    tracer, client = _get_tracer_and_client("songdb")
    writer = tracer.writer
    db = client["testdb"]
    db.drop_collection("songs")
    input_songs = [
        {'name' : 'Powderfinger', 'artist':'Neil'},
        {'name' : 'Harvest', 'artist':'Neil'},
        {'name' : 'Suzanne', 'artist':'Leonard'},
        {'name' : 'Partisan', 'artist':'Leonard'},
    ]
    db.songs.insert_many(input_songs)

    # test delete one
    af = {'artist':'Neil'}
    eq_(db.songs.count(af), 2)
    db.songs.delete_one(af)
    eq_(db.songs.count(af), 1)

    # test delete many
    af = {'artist':'Leonard'}
    eq_(db.songs.count(af), 2)
    db.songs.delete_many(af)
    eq_(db.songs.count(af), 0)

    # ensure all is traced.
    spans = writer.pop()
    assert spans, spans
    for span in spans:
        # ensure all the of the common metadata is set
        eq_(span.service, "songdb")
        eq_(span.span_type, "mongodb")
        eq_(span.meta.get("mongodb.collection"), "songs")
        eq_(span.meta.get("mongodb.db"), "testdb")
        assert span.meta.get("out.host")
        assert span.meta.get("out.port")

    expected_resources = [
        "drop songs",
        "count songs",
        "count songs",
        "count songs",
        "count songs",
        'delete songs {"artist": "?"}',
        'delete songs {"artist": "?"}',
        "insert songs",
    ]

    eq_(sorted(expected_resources), sorted(s.resource for s in spans))


def test_insert_find():
    tracer, client = _get_tracer_and_client("pokemongodb")
    writer = tracer.writer

    start = time.time()
    db = client.testdb
    db.drop_collection("teams")
    teams = [
        {
            'name' : 'Toronto Maple Leafs',
            'established' : 1917,
        },
        {
            'name' : 'Montreal Canadiens',
            'established' : 1910,
        },
        {
            'name' : 'New York Rangers',
            'established' : 1926,
        }
    ]

    # create some data (exercising both ways of inserting)

    db.teams.insert_one(teams[0])
    db.teams.insert_many(teams[1:])

    # wildcard query (using the [] syntax)
    cursor = db["teams"].find()
    count = 0
    for row in cursor:
        count += 1
    eq_(count, len(teams))

    # scoped query (using the getattr syntax)
    q = {"name": "Toronto Maple Leafs"}
    queried = list(db.teams.find(q))
    end = time.time()
    eq_(len(queried), 1)
    eq_(queried[0]["name"], "Toronto Maple Leafs")
    eq_(queried[0]["established"], 1917)

    spans = writer.pop()
    for span in spans:
        # ensure all the of the common metadata is set
        eq_(span.service, "pokemongodb")
        eq_(span.span_type, "mongodb")
        eq_(span.meta.get("mongodb.collection"), "teams")
        eq_(span.meta.get("mongodb.db"), "testdb")
        assert span.meta.get("out.host"), span.pprint()
        assert span.meta.get("out.port"), span.pprint()
        assert span.start > start
        assert span.duration < end - start

    expected_resources = [
        "drop teams",
        "insert teams",
        "insert teams",
        "query teams {}",
        'query teams {"name": "?"}',
    ]

    eq_(sorted(expected_resources), sorted(s.resource for s in spans))

def _get_tracer_and_client(service):
    """ Return a tuple of (tracer, mongo_client) for testing. """
    tracer = Tracer()
    writer = DummyWriter()
    tracer.writer = writer
    original_client = MongoClient()
    client = trace_mongo_client(original_client, tracer, service=service)
    return tracer, client


