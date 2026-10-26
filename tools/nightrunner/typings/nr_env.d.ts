// NIGHT RUNNER: Minecraft 統合版のスクリプト環境にある「ES 標準以外」のグローバルだけを書く。
//
// tsconfig.nr.json は lib を ES2022 だけにしている（DOM・Node を入れない）。
// だから setTimeout / setInterval / window / document / fetch / require / process / Buffer
// などを使うと型検査で「Cannot find name」になる。ゲームの中にも無いので、それで正しい。
//   遅延・繰り返しは system.runTimeout / system.runInterval / system.runJob を使う。
// ゲームにあるのは console（出力はコンテンツログ）くらい。ここに足すのは実機にあると確かめたものだけ。

interface NrConsole {
    log(...data: any[]): void;
    info(...data: any[]): void;
    warn(...data: any[]): void;
    error(...data: any[]): void;
}

declare var console: NrConsole;
