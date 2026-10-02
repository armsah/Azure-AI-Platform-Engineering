import express from "express"
import type { Request, Response } from "express";

const app = express();
const port = Number(process.env.PORT ?? 3000);

app.get("/health", (_req: Request, res: Response) => {
    res.status(200).json({
        status: "healthy",
        service: "node-api",
    });
});

app.listen(port, () => {
    console.log(`node-api listening on port ${port}`);
});