# CSOKi Quick Import Bookmarklet

## What It Does
Allows you to import any Crexi/LoopNet listing with ONE CLICK while browsing.

## Installation

### Step 1: Create the Bookmarklet
1. Copy the code below
2. Create a new bookmark in your browser
3. Paste the code as the URL
4. Name it "Add to CSOKi"

### Bookmarklet Code (Version 1 - Simple)

```javascript
javascript:(function(){const url=window.location.href;const apiUrl='https://backend-production-cf26.up.railway.app/api/v1/listings/import-url';fetch(apiUrl,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:url,use_playwright:true,save_to_database:true})}).then(r=>r.json()).then(data=>{if(data.success){alert(`✅ Added to CSOKi!\n\n${data.title||'Listing'}\n${data.address||''}\nConfidence: ${data.confidence}%`);}else{alert(`❌ Failed to import\n\n${data.error_message||'Unknown error'}`);}}).catch(err=>{alert('❌ Error: '+err.message);});})();
```

### Bookmarklet Code (Version 2 - With Preview)

```javascript
javascript:(function(){const url=window.location.href;const apiUrl='https://backend-production-cf26.up.railway.app/api/v1/listings/import-url';const popup=window.open('','CSOKi Import','width=600,height=700,resizable=yes');popup.document.write('<html><head><title>CSOKi Import</title><style>body{font-family:system-ui,sans-serif;padding:20px;background:#f5f5f5}h2{color:#333}.loading{text-align:center;padding:40px}.field{margin:10px 0;padding:10px;background:white;border-radius:4px}.label{font-weight:bold;color:#666;font-size:12px}.value{margin-top:4px}.confidence{display:inline-block;padding:4px 8px;border-radius:4px;font-weight:bold;color:white;margin-top:10px}.high{background:#22c55e}.medium{background:#f59e0b}.low{background:#ef4444}button{padding:12px 24px;margin:10px 5px 0 0;border:none;border-radius:6px;font-size:14px;cursor:pointer;font-weight:600}.save{background:#22c55e;color:white}.cancel{background:#6b7280;color:white}</style></head><body><div class="loading"><h2>⚡ Extracting data...</h2><p>Please wait while we analyze the listing.</p></div></body></html>');fetch(apiUrl,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:url,use_playwright:true,save_to_database:false})}).then(r=>r.json()).then(data=>{let confClass='low';if(data.confidence>=80)confClass='high';else if(data.confidence>=60)confClass='medium';let html=`<h2>📋 Review Listing</h2>`;if(data.success){html+=`<div class="field"><div class="label">TITLE</div><div class="value">${data.title||'(no title)'}</div></div><div class="field"><div class="label">ADDRESS</div><div class="value">${data.address||'(no address)'}</div><div class="value">${data.city||''}, ${data.state||''} ${data.postal_code||''}</div></div><div class="field"><div class="label">PRICE</div><div class="value">${data.price_display||data.price||'Contact for Pricing'}</div></div><div class="field"><div class="label">PROPERTY TYPE</div><div class="value">${data.property_type||'(unknown)'}</div></div><div class="field"><div class="label">SIZE</div><div class="value">${data.sqft?data.sqft.toLocaleString()+' SF':''} ${data.lot_size_acres?data.lot_size_acres+' AC':''}</div></div><div class="confidence ${confClass}">Confidence: ${data.confidence}%</div><br><button class="save" onclick="saveIt()">💾 Save to CSOKi</button><button class="cancel" onclick="window.close()">❌ Cancel</button>`;html+=`<script>function saveIt(){document.body.innerHTML='<div class=loading><h2>💾 Saving...</h2></div>';fetch('${apiUrl}',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:'${url}',use_playwright:true,save_to_database:true})}).then(r=>r.json()).then(result=>{if(result.success){document.body.innerHTML='<div style=text-align:center;padding:40px><h2 style=color:#22c55e>✅ Saved!</h2><p>Listing #'+result.listing_id+'</p><button onclick=window.close() style=padding:10px 20px;margin-top:20px;background:#22c55e;color:white;border:none;border-radius:6px;cursor:pointer>Close</button></div>';}else{document.body.innerHTML='<div style=text-align:center;padding:40px><h2 style=color:#ef4444>❌ Failed</h2><p>'+result.error_message+'</p><button onclick=window.close() style=padding:10px 20px;margin-top:20px;background:#6b7280;color:white;border:none;border-radius:6px;cursor:pointer>Close</button></div>';}}).catch(err=>{alert('Error: '+err.message);});}</script>`;}else{html=`<h2 style=color:#ef4444>❌ Extraction Failed</h2><p>${data.error_message||'Could not extract listing data from this page.'}</p><button class="cancel" onclick="window.close()">Close</button>`;}popup.document.body.innerHTML=html;}).catch(err=>{popup.document.body.innerHTML=`<div style=text-align:center;padding:40px><h2 style=color:#ef4444>❌ Error</h2><p>${err.message}</p><button onclick=window.close() style=padding:10px 20px;margin-top:20px;background:#6b7280;color:white;border:none;border-radius:6px;cursor:pointer>Close</button></div>`;});})();
```

## How to Use

1. **While browsing Crexi or LoopNet**, click the "Add to CSOKi" bookmark
2. The bookmarklet will:
   - Extract all listing data automatically
   - Show you a preview (Version 2 only)
   - Save to your CSOKi database
3. **Done!** Listing is now in your dashboard

## Features

**Version 1 (Simple):**
- ✅ One-click add
- ✅ Instant confirmation
- ✅ No preview, just saves

**Version 2 (Preview):**
- ✅ Shows extracted data before saving
- ✅ Review/confirm accuracy
- ✅ Confidence score indicator
- ✅ Better UX

## Supported Sites

- ✅ Crexi
- ✅ LoopNet
- ⚠️ Other CRE sites (may work, lower confidence)

## Troubleshooting

**"Failed to import"**
- The page might be JavaScript-heavy (use Version 1 with `use_playwright:true`)
- Check if listing is public/accessible

**"Error: CORS"**
- This is expected - browser security
- The listing was likely still imported (check your dashboard)

**Low confidence score (<60%)**
- Review the extracted data carefully
- Some fields may be missing
- You can manually edit in the dashboard

## Next Steps

Once this is working, we can:
1. Add browser extension for better UX
2. Build batch import UI
3. Add email parsing for automated alerts

---

**Created by Flash** ⚡  
February 3, 2026
