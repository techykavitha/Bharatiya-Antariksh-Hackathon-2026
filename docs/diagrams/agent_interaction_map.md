# Agent Interaction Map

> **Version:** 0.3.0 | **Last Updated:** 2026-07-09

```mermaid
flowchart TB
    subgraph Environmental
        FA[flood_agent]
        HA[heatwave_agent]
        AQ[air_quality_agent]
    end

    subgraph Infrastructure
        WA[water_resource_agent]
        UP[urban_planning_agent]
        AG[agriculture_agent]
    end

    subgraph Emergency
        CY[cyclone_agent]
        DR[disaster_response_agent]
    end

    CY -->|storm surge flooding| FA
    CY -->|emergency coordination| DR
    CY -->|post-landfall pollution| AQ

    FA -->|crop damage| AG
    FA -->|drainage planning| UP
    FA -->|multi-hazard| DR

    HA -->|compound heat-AQI| AQ
    HA -->|crop heat stress| AG
    HA -->|UHI mitigation| UP

    AQ -->|urban mitigation| UP
    AQ -->|health emergency| DR
    AQ -->|stubble burning| AG

    WA -->|irrigation advisory| AG
    WA -->|water security| UP

    DR -->|consult| FA
    DR -->|consult| CY
    DR -->|consult| HA
    DR -->|consult| AQ
```

## Communication Contract

All inter-agent calls use `AgentCommunicationInterface.call_agent()` with normalized `PeerAgentOutput` payloads. No direct module imports between agent packages.
