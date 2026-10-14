import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import type { AddressInfo } from "node:net";
import type { Server } from "node:http";
import { app } from "../app.js";

let server: Server;
let baseUrl: string;

before(async () => {
    server = app.listen(0);

    await new Promise<void>((resolve, reject) => {
        if (server.listening) {
            resolve();
            return;
        }

        server.once("listening", resolve);
        server.once("error", reject);
    });

    const address = server.address() as AddressInfo;
    baseUrl = `http://127.0.0.1:${address.port}`;
});

after(async () => {
    if (server) {
        await new Promise<void>((resolve, reject) => {
            server.close((error) => {
                if (error) reject(error);
                else resolve();
            });
        });
    }
});

test("GET /health returns HTTP 200", async () => {
    const response = await fetch(`${baseUrl}/health`);
    assert.equal(response.status, 200);
});

test("GET /health returns the expected service contract", async () => {
    const response = await fetch(`${baseUrl}/health`);
    const body = await response.json();

    assert.deepEqual(body, {
        status: "healthy",
        service: "node-api",
    });
});

test("GET /health returns JSON", async () => {
    const response = await fetch(`${baseUrl}/health`);

    assert.match(
        response.headers.get("content-type") ?? "",
        /^application\/json/
    );
});

test("unknown routes return HTTP 404", async () => {
    const response = await fetch(`${baseUrl}/does-not-exist`);
    assert.equal(response.status, 404);
});
