"""
Builds the data snapshot for the single pane of glass view.

Tries a live pull from VTAP and Enterpryze if credentials are configured
(see vtap_client.py / enterpryze_client.py for the env vars each needs).
Falls back to labelled sample data, shaped exactly like the real API
responses, if either system isn't configured yet -- so the same
downstream code and the same HTML render either way. Re-run this any
time credentials are added or data should be refreshed.
"""
import json
import datetime
from vtap_client import VTAPClient
from enterpryze_client import EnterpryzeClient

# ---------------------------------------------------------------------------
# Sample data: field-accurate to the two specs, standing in until live
# credentials exist. Deliberately includes an imperfect name match and an
# unmatched customer, because that's the real state of the join today.
# ---------------------------------------------------------------------------

SAMPLE_VTAP_CUSTOMERS = [
    {
        "cid": "C00412", "custname": "EoS Fitness", "custaddr": "1180 N Town Center Dr, Las Vegas, NV",
        "country": "US", "billingcurrency": "USD", "billingentity": "Dot Inc",
        "custstatus": "active", "billingvat": None, "custinternal": 0,
    },
    {
        "cid": "C00187", "custname": "PassEntry", "custaddr": "14 Charlotte Rd, London",
        "country": "GB", "billingcurrency": "GBP", "billingentity": "Dot Limited",
        "custstatus": "active", "billingvat": "GB123456789", "custinternal": 0,
    },
    {
        "cid": "C01033", "custname": "Harbor Wellness Studio", "custaddr": "22 Harbor Way, Portland, ME",
        "country": "US", "billingcurrency": "USD", "billingentity": "Dot Inc",
        "custstatus": "active", "billingvat": None, "custinternal": 0,
    },
]

SAMPLE_VTAP_READERS = [
    {"rid": "R88301", "cid": "C00412", "fid": "F0091", "fleetname": "EoS - Summerlin", "location": "Front desk",
     "appparam1": None, "appparam2": None, "lasttaptime": "2026-08-11 09:14:02", "active": "yes"},
    {"rid": "R88302", "cid": "C00412", "fid": "F0092", "fleetname": "EoS - Henderson", "location": "Front desk",
     "appparam1": None, "appparam2": None, "lasttaptime": "2026-08-11 07:52:41", "active": "yes"},
    {"rid": "R88303", "cid": "C00412", "fid": None, "fleetname": None, "location": "Charge / For June?",
     "appparam1": None, "appparam2": None, "lasttaptime": None, "active": "yes"},
    {"rid": "R71190", "cid": "C00187", "fid": "F0033", "fleetname": "PassEntry - Dear Darling", "location": None,
     "appparam1": "door_north", "appparam2": "venue=Dear Darling", "lasttaptime": "2026-08-10 22:03:11", "active": "yes"},
    {"rid": "R71191", "cid": "C00187", "fid": "F0034", "fleetname": "PassEntry - Mama Roux", "location": None,
     "appparam1": "door_main", "appparam2": "venue=Mama Roux", "lasttaptime": "2026-08-10 23:41:55", "active": "yes"},
    {"rid": "R90410", "cid": "C01033", "fid": None, "fleetname": None, "location": "Reception",
     "appparam1": None, "appparam2": None, "lasttaptime": "2026-07-30 15:02:09", "active": "yes"},
]

SAMPLE_ENTERPRYZE_BPS = [
    {"cardCode": "BP-0512", "name": "EoS Fitness Ltd", "billToCity": "Las Vegas", "billToCountry": "US"},
    {"cardCode": "BP-0299", "name": "PassEntry Limited", "billToCity": "London", "billToCountry": "GB"},
    # Note: nothing for Harbor Wellness Studio -- it isn't in Enterpryze yet, on the sample data at least.
]

SAMPLE_ENTERPRYZE_INVOICES = [
    {"_id": "INV-51820", "bpCode": "BP-0512", "bpName": "EoS Fitness Ltd", "amountPaid": 4820.00, "cancelled": False},
    {"_id": "INV-51821", "bpCode": "BP-0299", "bpName": "PassEntry Limited", "amountPaid": 340.00, "cancelled": False},
]

# ---------------------------------------------------------------------------
# Field status: what the tracker says about each field right now.
# status one of: confirmed / needs_cr / open_question / in_progress
# ---------------------------------------------------------------------------

FIELD_STATUS = [
    {"system": "VTAP", "field": "cid / custname", "status": "confirmed", "ref": None,
     "note": "Available today, read only."},
    {"system": "VTAP", "field": "billingentity", "status": "needs_cr", "ref": "CR7",
     "note": "Free text today; four spellings found for what may be two entities."},
    {"system": "VTAP", "field": "External accounting reference (link to Enterpryze cardCode)", "status": "needs_cr",
     "ref": "CR2 / CR3", "note": "Field doesn't exist yet, and the customer record is read only via the API. This is the actual join key."},
    {"system": "VTAP", "field": "fid / fleetname (Fleet)", "status": "confirmed", "ref": None,
     "note": "Exists today. Confirmed 12 Aug as the primary attribute for which customer a reader belongs to."},
    {"system": "VTAP", "field": "Fleet assignment coverage", "status": "open_question", "ref": "Q26 / Q29 / Q35",
     "note": "Fleets are 'sometimes' used, not enforced at registration. R88303 and R90410 below show the gap."},
    {"system": "VTAP", "field": "appparam1 / appparam2", "status": "confirmed", "ref": None,
     "note": "Exist today, but customer-configurable and explicitly not reliable for billing (confirmed 12 Aug)."},
    {"system": "VTAP", "field": "lasttaptime", "status": "confirmed", "ref": None,
     "note": "Available today, but overwritten on every tap -- the activation moment isn't preserved."},
    {"system": "VTAP", "field": "first_tap_time (write-once)", "status": "needs_cr", "ref": "CR1",
     "note": "Doesn't exist yet. The single highest-value change request on the tracker."},
    {"system": "VTAP", "field": "local_mode flag", "status": "needs_cr", "ref": "CR6",
     "note": "Currently inferred from free text notes."},
    {"system": "VTAP", "field": "TRIAL state", "status": "needs_cr", "ref": "CR12",
     "note": "DEV exists and never expires; a time-boxed converting state doesn't exist yet."},
    {"system": "VTAP", "field": "Payer reference (where payer differs from customer of record)", "status": "needs_cr",
     "ref": "CR13", "note": "Evidence for the need exists on the Retired sheet ('Who pays subscription')."},
    {"system": "Enterpryze", "field": "cardCode / name", "status": "confirmed", "ref": None,
     "note": "Business Partner primary key, exists today."},
    {"system": "Enterpryze", "field": "API access enabled", "status": "in_progress", "ref": None,
     "note": "Confirmed 12 Aug -- Tim can get this enabled. No longer blocked, not yet done."},
    {"system": "Enterpryze", "field": "Read/write scope", "status": "open_question", "ref": "Q20",
     "note": "Whether invoice paid status can be read back, which is what closes the loop for dunning."},
    {"system": "Enterpryze", "field": "Webhooks vs poll-only", "status": "open_question", "ref": "Q21", "note": None},
    {"system": "Enterpryze", "field": "Custom field for VTAP customer id", "status": "open_question", "ref": "Q22",
     "note": "This is what CR2 actually needs on the other side to close the loop."},
    {"system": "Enterpryze", "field": "Native recurring billing", "status": "open_question", "ref": "Q23",
     "note": "If one-off only, the middleware owns the billing schedule as real scope."},
    {"system": "Enterpryze", "field": "Sales invoice amountPaid / cancelled", "status": "confirmed", "ref": None,
     "note": "Exists today."},
]


def name_key(s):
    return "".join(ch.lower() for ch in (s or "") if ch.isalnum())


def build():
    vtap = VTAPClient()
    ent = EnterpryzeClient()

    live = vtap.configured and ent.configured
    source_note = "Live" if live else "Sample data -- VTAP and/or Enterpryze credentials not yet configured"

    if live:
        customers = vtap.list_customers().get("data", [])
        readers = vtap.list_readers().get("data", [])
        bps = ent.list_business_partners()
        invoices = ent.list_sales_invoices()
    else:
        customers = SAMPLE_VTAP_CUSTOMERS
        readers = SAMPLE_VTAP_READERS
        bps = SAMPLE_ENTERPRYZE_BPS
        invoices = SAMPLE_ENTERPRYZE_INVOICES

    bp_by_name = {name_key(b["name"]): b for b in bps}
    inv_by_bp = {}
    for inv in invoices:
        inv_by_bp.setdefault(inv["bpCode"], []).append(inv)

    correlated = []
    for c in customers:
        c_readers = [r for r in readers if r["cid"] == c["cid"]]
        fleet_count = len({r["fid"] for r in c_readers if r.get("fid")})
        no_fleet = [r["rid"] for r in c_readers if not r.get("fid")]

        match = bp_by_name.get(name_key(c["custname"]))
        if match:
            join_status = "matched_by_name"
            join_note = f"Matched Enterpryze '{match['name']}' by name. No stored key yet (CR2) -- this match is not guaranteed stable."
            bp_invoices = inv_by_bp.get(match["cardCode"], [])
        else:
            join_status = "unmatched"
            join_note = "No Enterpryze Business Partner found by name. Either not yet created there, or the names genuinely differ."
            bp_invoices = []

        correlated.append({
            "vtap_customer": c,
            "reader_count": len(c_readers),
            "fleet_count": fleet_count,
            "readers_without_fleet": no_fleet,
            "readers": c_readers,
            "enterpryze_match": match,
            "join_status": join_status,
            "join_note": join_note,
            "invoices": bp_invoices,
        })

    snapshot = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "source": source_note,
        "live": live,
        "correlated": correlated,
        "field_status": FIELD_STATUS,
    }
    return snapshot


if __name__ == "__main__":
    snap = build()
    with open("snapshot.json", "w") as f:
        json.dump(snap, f, indent=2)
    print("wrote snapshot.json —", snap["source"])
    print(f"{len(snap['correlated'])} customers correlated")
