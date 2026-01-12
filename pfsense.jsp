<%@ page contentType="text/plain; charset=UTF-8" %>
<%@ page import="java.io.*, java.util.*, org.json.*" %>
<%! 
    // State managed in RAM (Application Scope)
    long lastReadTime = 0;
    JSONObject cachedJson = null;
    private final Object lock = new Object();
%>
<%
    String path = application.getRealPath("/") + "master_infrastructure_db.json";
    File dbFile = new File(path);

    // 1. SMART RELOAD: Check if file exists and if it's newer than our cache
    if (!dbFile.exists()) {
        out.println("Error: master_infrastructure_db.json not found.");
        return;
    }

    if (cachedJson == null || dbFile.lastModified() > lastReadTime) {
        synchronized(lock) {
            if (dbFile.lastModified() > lastReadTime) {
                try {
                    String content = new Scanner(dbFile).useDelimiter("\\Z").next();
                    cachedJson = new JSONObject(content);
                    lastReadTime = dbFile.lastModified();
                    System.out.println("API LOG: master_infrastructure_db.json reloaded into memory.");
                } catch (Exception e) {
                    out.println("Error parsing JSON: " + e.getMessage());
                    return;
                }
            }
        }
    }

// 2. PROCESS REQUEST
    String targetDomain = request.getParameter("domain");
    String targetSub = request.getParameter("subdomain"); // New parameter

    if (targetDomain == null || targetDomain.trim().isEmpty()) {
        out.println("Error: Please provide a ?domain= parameter.");
        return;
    }

    try {
        JSONObject domains = cachedJson.getJSONObject("domains");
        if (domains.has(targetDomain)) {
            JSONObject history = domains.getJSONObject(targetDomain).getJSONObject("history");
            Set<String> ipList = new TreeSet<>();

            // Decide if we are looking at ONE subdomain or ALL of them
            List<String> subsToProcess = new ArrayList<>();
            if (targetSub != null && !targetSub.trim().isEmpty()) {
                if (history.has(targetSub)) {
                    subsToProcess.add(targetSub);
                } else {
                    out.println("Subdomain [" + targetSub + "] not found for " + targetDomain);
                    return;
                }
            } else {
                // No subdomain specified? Grab the keys for all of them
                subsToProcess.addAll(history.keySet());
            }

            for (String sub : subsToProcess) {
                JSONArray records = history.getJSONArray(sub);
                
                // N, N-1 Logic: Get last two snapshots
                int start = Math.max(0, records.length() - 2);
                for (int i = start; i < records.length(); i++) {
                    JSONArray ips = records.getJSONObject(i).getJSONArray("ips");
                    for (int j = 0; j < ips.length(); j++) {
                        ipList.add(ips.getString(j));
                    }
                }
            }

            // Output clean list for pfSense
            for (String ip : ipList) {
                out.println(ip);
            }
        } else {
            out.println("Domain [" + targetDomain + "] not found in database.");
        }
    } catch (Exception e) {
        out.println("Application Error: " + e.getMessage());
    }
%>
