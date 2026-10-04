using OpenTelemetry.Resources;
using OpenTelemetry.Trace;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource
        .AddService("dotnet-api"))
    .WithTracing(tracing => tracing
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter());

builder.Services.AddHttpClient();

var app = builder.Build();

app.MapGet("/health", () => Results.Ok(new
{
    status = "healthy",
    service = "dotnet-api"
}));

app.MapGet("/trace-demo", async (IHttpClientFactory factory) =>
{
    var javaUrl =
        Environment.GetEnvironmentVariable("JAVA_API_URL")
        ?? "http://localhost:8081";

    var client = factory.CreateClient();

    var downstream = await client.GetFromJsonAsync<object>(
        $"{javaUrl}/trace-demo"
    );

    return Results.Ok(new
    {
        service = "dotnet-api",
        downstream
    });
});

app.Run();
