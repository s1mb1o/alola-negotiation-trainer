"""Validate actual HTTP responses, including routes that return JSONResponse directly."""

import re

from jsonschema import Draft202012Validator


def schema_validator(document, schema):
    return Draft202012Validator({"components": document["components"], **schema})


class ResponseContractCheck:
    def __init__(self, app):
        self.app = app
        self.operations = None
        self.seen = set()

    def __call__(self, response):
        path = response.request.url.path
        if not path.startswith("/api/v1/"):
            return
        if self.operations is None:
            document = self.app.openapi()
            self.operations = []
            for route, methods in document["paths"].items():
                pattern = re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", route) + "$")
                for method, operation in methods.items():
                    validators = {
                        status: schema_validator(
                            document, item["content"]["application/json"]["schema"]
                        )
                        for status, item in operation["responses"].items()
                    }
                    self.operations.append(
                        (pattern, method.upper(), operation["operationId"], validators)
                    )
        for pattern, method, operation_id, validators in self.operations:
            if method == response.request.method and pattern.fullmatch(path):
                status = str(response.status_code)
                assert status in validators, f"Undocumented {operation_id} status {status}"
                response.read()
                errors = list(validators[status].iter_errors(response.json()))
                assert not errors, "\n".join(
                    f"{operation_id} {status} {list(error.absolute_path)}: {error.message}"
                    for error in errors
                )
                self.seen.add((operation_id, status))
                return
        raise AssertionError(f"Undocumented canonical operation: {response.request.method} {path}")
