import express from "express";
import type { Request, Response } from "express";

export const app = express();

app.get("/health", (_req: Request, res: Response) => {
    res.status(200).json({
        status: "healthy",
        service: "node-api",
    });
});
