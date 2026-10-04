# Demo prompts

Prompts for testing the server in Claude Desktop or Claude Code and for recording the README GIF. Expected tool calls in brackets.

1. "Which installations belong to the Itaqui port complex?" [find_installation]
2. "Give me the profile of Itaqui from 2019 to 2025 and tell me what changed in waiting time." [port_profile]
3. "Rank Itaqui, Paranaguá, Santos and Ponta da Madeira by waiting time to berth in 2025." [compare_ports]
4. "Compare cargo at Itaqui in 2025 and 2026." [compare_ports, Claude should warn that 2026 is partial]
5. "A 45,000 DWT tanker stayed 67 hours at berth in Itaqui. How much CO2 would shore power avoid? Explain the method." [estimate_berth_co2, explain_method]
6. "Using Itaqui's mean hours at berth in 2025, estimate the CO2 of a small, a medium and a large tanker call." [port_profile, estimate_calls_co2]
7. "How many berthings did Paranaguá have in 2025?" [resolve exact name to BRPNG, not Cattalini]

Recording tip: prompt 6 is the best for the GIF, because Claude chains the port data and the CO2 tool in one answer.
