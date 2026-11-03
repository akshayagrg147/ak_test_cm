import io
import ssl
import subprocess
import sys

import certifi
from pypdf import PdfWriter

from conftest import make_lead


# Upstream regression for GHSA-5849-834g-hvw5: an xref section without a trailer.
MALFORMED_TRAILER_PDF = b"%PDF-1.4\nstartxref\n28\n%%EOF\nxref\n1 0\naaa"


def test_pdf_trailer_regression_is_rejected_without_hanging_or_saving_a_file(env):
    # Run the real validator outside pytest first. Reintroducing the vulnerable
    # parser must fail within a bound, rather than freeze the test/API worker.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import io
import sys
from fastapi import HTTPException
from pypdf import PdfWriter
from app.files import validate_content

writer = PdfWriter()
writer.add_blank_page(width=72, height=72)
output = io.BytesIO()
writer.write(output)
validate_content(output.getvalue(), "application/pdf")
print("valid-pdf-accepted", flush=True)

try:
    validate_content(sys.stdin.buffer.read(), "application/pdf")
except HTTPException as error:
    assert error.status_code == 422
    assert error.detail["code"] == "invalid_content"
    print("malformed-pdf-rejected", flush=True)
else:
    raise AssertionError("Malformed PDF must be rejected")
""",
        ],
        input=MALFORMED_TRAILER_PDF,
        capture_output=True,
        timeout=10,
        check=True,
    )
    assert result.stdout.splitlines() == [b"valid-pdf-accepted", b"malformed-pdf-rejected"]

    # Only exercise the API after bounded validation succeeds. An unsafe parser
    # cannot reach an unbounded in-process TestClient call on regression.
    clients, _ = env
    lead = make_lead(clients["caller"])
    path = f"/api/leads/{lead['id']}/files"
    rejected = clients["caller"].post(
        path, files={"file": ("broken-trailer.pdf", MALFORMED_TRAILER_PDF, "application/pdf")}
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "invalid_content"
    history = clients["caller"].get(f"/api/leads/{lead['id']}/history")
    assert history.status_code == 200
    assert history.json()["files"] == []

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    output = io.BytesIO()
    writer.write(output)
    accepted = clients["caller"].post(
        path, files={"file": ("valid-after-rejection.pdf", output.getvalue(), "application/pdf")}
    )
    assert accepted.status_code == 201, accepted.text
    downloaded = clients["caller"].get(f"/api/files/{accepted.json()['id']}")
    assert downloaded.status_code == 200
    assert downloaded.content == output.getvalue()


def test_https_ca_bundle_does_not_trust_the_compromised_emsign_root():
    context = ssl.create_default_context(cafile=certifi.where())
    common_names = {
        value
        for certificate in context.get_ca_certs()
        for rdn in certificate.get("subject", ())
        for key, value in rdn
        if key == "commonName"
    }
    assert common_names, "The application must retain a usable CA trust bundle"
    assert "emSign ECC Root CA - G3" not in common_names
