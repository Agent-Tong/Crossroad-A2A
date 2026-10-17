# spec/

Illustrative JSON Schemas (draft 2020-12) for the shapes Crossroad moves around, with examples that validate.

| File | Describes |
|---|---|
| `letter.schema.json` | a letter envelope (call id, sender, receiver, purpose, hop, parent, body) |
| `answer.schema.json` | an answer to one letter (parent call id, purpose `answer`, body, origin) |
| `island.schema.json` | an island and its post office |
| `member.schema.json` | an agent, how it is woken or pulls, and what it may do |
| `policy.schema.json` | a signed policy: islands, members, routes |
| `examples/*.json` | one valid example of each, with placeholder values only |
| `validate_examples.py` | stdlib check: every example validates, every bad variant is rejected |

Field names match the docs and the reference code. These schemas are a reading aid, not the wire format of a particular release: real policy files carry more fields. Run `python3 -I -B spec/validate_examples.py`.

Not in these schemas: the envelope's cryptographic fields (signature scheme, keys, canonicalisation) and the wire format of the peer-data fence. Both are outside these illustrative schemas. The fence as the reference code writes it is shown in the top-level README and in `reference/dropbox-port/dropbox_port.py`; the signature handling is summarised in [../docs/TRUST_RULES.md](../docs/TRUST_RULES.md).

Length note: `maxLength` in these schemas counts characters. The answer cap in the reference bridge is 8000 UTF-8 bytes and is enforced by application code, not by the schema. Incoming letters have transport-specific payload/file limits; 8192 characters in letter.schema.json is illustrative, not an 8000-byte incoming body guarantee. The validator shows the difference (4001 two-byte characters pass the schema's character check and fail the byte check) but does not prove byte-limit conformance of any implementation.
