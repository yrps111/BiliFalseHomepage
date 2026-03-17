// ===== B站视频爬取 - 浏览器控制台脚本 =====
// 用于爬取第101页以后的视频（Python脚本受100页限制）
//
// 使用方法:
// 1. 用Chrome打开任意B站页面（需要已登录）
// 2. 按F12打开开发者工具 → Console(控制台)标签
// 3. 修改下方 MID、START_PAGE、END_PAGE
// 4. 粘贴此脚本并回车运行
// 5. 等待完成后会自动下载JSON文件
// =============================================

(async function() {
    // ===== 配置（修改此处） =====
    const MID = "0";          // ← 替换为目标UP主的UID
    const START_PAGE = 101;   // 起始页（通常从101开始）
    const END_PAGE = 200;     // 结束页（总视频数 ÷ 30，向上取整）
    const ORDER = "pubdate";  // 排序方式
    const DELAY_MS = 1200;    // 每次请求间隔(毫秒)

    if (MID === "0") {
        console.error("请先修改 MID 为目标UP主的UID");
        return;
    }

    // WBI签名所需的置换表
    const MIXIN = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52];

    // MD5实现(浏览器环境没有hashlib，需要纯JS实现)
    function md5(string) {
        function md5cycle(x, k) {
            var a = x[0], b = x[1], c = x[2], d = x[3];
            a = ff(a, b, c, d, k[0], 7, -680876936); d = ff(d, a, b, c, k[1], 12, -389564586);
            c = ff(c, d, a, b, k[2], 17, 606105819); b = ff(b, c, d, a, k[3], 22, -1044525330);
            a = ff(a, b, c, d, k[4], 7, -176418897); d = ff(d, a, b, c, k[5], 12, 1200080426);
            c = ff(c, d, a, b, k[6], 17, -1473231341); b = ff(b, c, d, a, k[7], 22, -45705983);
            a = ff(a, b, c, d, k[8], 7, 1770035416); d = ff(d, a, b, c, k[9], 12, -1958414417);
            c = ff(c, d, a, b, k[10], 17, -42063); b = ff(b, c, d, a, k[11], 22, -1990404162);
            a = ff(a, b, c, d, k[12], 7, 1804603682); d = ff(d, a, b, c, k[13], 12, -40341101);
            c = ff(c, d, a, b, k[14], 17, -1502002290); b = ff(b, c, d, a, k[15], 22, 1236535329);
            a = gg(a, b, c, d, k[1], 5, -165796510); d = gg(d, a, b, c, k[6], 9, -1069501632);
            c = gg(c, d, a, b, k[11], 14, 643717713); b = gg(b, c, d, a, k[0], 20, -373897302);
            a = gg(a, b, c, d, k[5], 5, -701558691); d = gg(d, a, b, c, k[10], 9, 38016083);
            c = gg(c, d, a, b, k[15], 14, -660478335); b = gg(b, c, d, a, k[4], 20, -405537848);
            a = gg(a, b, c, d, k[9], 5, 568446438); d = gg(d, a, b, c, k[14], 9, -1019803690);
            c = gg(c, d, a, b, k[3], 14, -187363961); b = gg(b, c, d, a, k[8], 20, 1163531501);
            a = gg(a, b, c, d, k[13], 5, -1444681467); d = gg(d, a, b, c, k[2], 9, -51403784);
            c = gg(c, d, a, b, k[7], 14, 1735328473); b = gg(b, c, d, a, k[12], 20, -1926607734);
            a = hh(a, b, c, d, k[5], 4, -378558); d = hh(d, a, b, c, k[8], 11, -2022574463);
            c = hh(c, d, a, b, k[11], 16, 1839030562); b = hh(b, c, d, a, k[14], 23, -35309556);
            a = hh(a, b, c, d, k[1], 4, -1530992060); d = hh(d, a, b, c, k[4], 11, 1272893353);
            c = hh(c, d, a, b, k[7], 16, -155497632); b = hh(b, c, d, a, k[10], 23, -1094730640);
            a = hh(a, b, c, d, k[13], 4, 681279174); d = hh(d, a, b, c, k[0], 11, -358537222);
            c = hh(c, d, a, b, k[3], 16, -722521979); b = hh(b, c, d, a, k[6], 23, 76029189);
            a = hh(a, b, c, d, k[9], 4, -640364487); d = hh(d, a, b, c, k[12], 11, -421815835);
            c = hh(c, d, a, b, k[15], 16, 530742520); b = hh(b, c, d, a, k[2], 23, -995338651);
            a = ii(a, b, c, d, k[0], 6, -198630844); d = ii(d, a, b, c, k[7], 10, 1126891415);
            c = ii(c, d, a, b, k[14], 15, -1416354905); b = ii(b, c, d, a, k[5], 21, -57434055);
            a = ii(a, b, c, d, k[12], 6, 1700485571); d = ii(d, a, b, c, k[3], 10, -1894986606);
            c = ii(c, d, a, b, k[10], 15, -1051523); b = ii(b, c, d, a, k[1], 21, -2054922799);
            a = ii(a, b, c, d, k[8], 6, 1873313359); d = ii(d, a, b, c, k[15], 10, -30611744);
            c = ii(c, d, a, b, k[6], 15, -1560198380); b = ii(b, c, d, a, k[13], 21, 1309151649);
            a = ii(a, b, c, d, k[4], 6, -145523070); d = ii(d, a, b, c, k[11], 10, -1120210379);
            c = ii(c, d, a, b, k[2], 15, 718787259); b = ii(b, c, d, a, k[9], 21, -343485551);
            x[0] = add32(a, x[0]); x[1] = add32(b, x[1]); x[2] = add32(c, x[2]); x[3] = add32(d, x[3]);
        }
        function cmn(q, a, b, x, s, t) { a = add32(add32(a, q), add32(x, t)); return add32((a << s) | (a >>> (32 - s)), b); }
        function ff(a, b, c, d, x, s, t) { return cmn((b & c) | ((~b) & d), a, b, x, s, t); }
        function gg(a, b, c, d, x, s, t) { return cmn((b & d) | (c & (~d)), a, b, x, s, t); }
        function hh(a, b, c, d, x, s, t) { return cmn(b ^ c ^ d, a, b, x, s, t); }
        function ii(a, b, c, d, x, s, t) { return cmn(c ^ (b | (~d)), a, b, x, s, t); }
        function md51(s) {
            var n = s.length, state = [1732584193, -271733879, -1732584194, 271733878], i;
            for (i = 64; i <= n; i += 64) { md5cycle(state, md5blk(s.substring(i - 64, i))); }
            s = s.substring(i - 64);
            var tail = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0];
            for (i = 0; i < s.length; i++) tail[i >> 2] |= s.charCodeAt(i) << ((i % 4) << 3);
            tail[i >> 2] |= 0x80 << ((i % 4) << 3);
            if (i > 55) { md5cycle(state, tail); tail = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]; }
            tail[14] = n * 8;
            md5cycle(state, tail);
            return state;
        }
        function md5blk(s) {
            var md5blks = [], i;
            for (i = 0; i < 64; i += 4) { md5blks[i >> 2] = s.charCodeAt(i) + (s.charCodeAt(i+1) << 8) + (s.charCodeAt(i+2) << 16) + (s.charCodeAt(i+3) << 24); }
            return md5blks;
        }
        var hex_chr = '0123456789abcdef'.split('');
        function rhex(n) { var s = '', j = 0; for (; j < 4; j++) s += hex_chr[(n >> (j * 8 + 4)) & 0x0f] + hex_chr[(n >> (j * 8)) & 0x0f]; return s; }
        function hex(x) { for (var i = 0; i < x.length; i++) x[i] = rhex(x[i]); return x.join(''); }
        function add32(a, b) { return (a + b) & 0xFFFFFFFF; }
        return hex(md51(string));
    }

    // 获取WBI密钥
    console.log("正在获取WBI密钥...");
    let navResp = await fetch("https://api.bilibili.com/x/web-interface/nav", {credentials: "include"});
    let navData = await navResp.json();
    let imgKey = navData.data.wbi_img.img_url.split("/").pop().split(".")[0];
    let subKey = navData.data.wbi_img.sub_url.split("/").pop().split(".")[0];
    let raw = imgKey + subKey;
    let mixinKey = MIXIN.map(i => raw[i]).join("").substring(0, 32);
    console.log("WBI密钥获取成功");

    function signParams(params) {
        params.wts = Math.floor(Date.now() / 1000).toString();
        let sorted = Object.keys(params).sort().reduce((o, k) => { o[k] = params[k]; return o; }, {});
        let query = new URLSearchParams(sorted).toString();
        sorted.w_rid = md5(query + mixinKey);
        return new URLSearchParams(Object.keys(sorted).sort().reduce((o, k) => { o[k] = sorted[k]; return o; }, {})).toString();
    }

    let allVideos = [];
    let failCount = 0;

    console.log(`开始爬取第 ${START_PAGE} 到 ${END_PAGE} 页...`);

    for (let pn = START_PAGE; pn <= END_PAGE; pn++) {
        let params = { mid: MID, ps: "30", tid: "0", pn: pn.toString(), order: ORDER };
        let queryStr = signParams(params);
        let url = "https://api.bilibili.com/x/space/wbi/arc/search?" + queryStr;

        try {
            let resp = await fetch(url, {credentials: "include"});
            if (resp.status === 412) {
                console.warn(`第 ${pn} 页: 412拦截! 等待5秒...`);
                failCount++;
                if (failCount > 5) { console.error("连续412过多，停止"); break; }
                await new Promise(r => setTimeout(r, 5000));
                pn--; // 重试
                continue;
            }
            let data = await resp.json();
            if (data.code !== 0) {
                console.warn(`第 ${pn} 页: code=${data.code}, 重试...`);
                failCount++;
                if (failCount > 8) { console.error("错误过多，停止"); break; }
                await new Promise(r => setTimeout(r, 3000));
                pn--;
                continue;
            }

            failCount = 0;
            let vlist = data.data.list.vlist;
            let totalPages = Math.ceil(data.data.page.count / 30);

            for (let v of vlist) {
                let ts = v.created || 0;
                let dur = v.length || "";
                allVideos.push({
                    bvid: v.bvid || "",
                    title: v.title || "",
                    play: v.play || 0,
                    danmaku: v.video_review || 0,
                    comment: v.comment || 0,
                    favorites: v.favorites || 0,
                    coin: v.coin || "",
                    like: v.like || "",
                    share: v.share || "",
                    pubdate: new Date(ts * 1000).toISOString().replace("T", " ").substring(0, 19),
                    pubdate_ts: ts,
                    duration: String(dur),
                    description: (v.description || "").replace(/\n/g, " ").replace(/\r/g, " "),
                    cover_url: v.pic || "",
                    link: "https://www.bilibili.com/video/" + (v.bvid || "") + "/"
                });
            }

            console.log(`第 ${pn}/${totalPages} 页: ${vlist.length} 条视频, 累计 ${allVideos.length} 条`);

        } catch(e) {
            console.error(`第 ${pn} 页出错: ${e.message}`);
            failCount++;
            if (failCount > 8) break;
            await new Promise(r => setTimeout(r, 3000));
            pn--;
            continue;
        }

        await new Promise(r => setTimeout(r, DELAY_MS));
    }

    // 下载结果为JSON
    console.log(`\n完成! 共获取 ${allVideos.length} 条视频`);
    let blob = new Blob([JSON.stringify(allVideos, null, 2)], {type: "application/json"});
    let a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `videos_page${START_PAGE}_plus.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    console.log(`JSON文件已下载: videos_page${START_PAGE}_plus.json`);
})();
