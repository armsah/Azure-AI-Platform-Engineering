import "./instrumentation.js";
import { app } from "./app.js";

const port = Number(process.env.PORT ?? 3000);

app.listen(port, () => {
    console.log(`node-api listening on port ${port}`);
});
