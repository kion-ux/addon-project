// ===========================================================================
//  超次元指南書 — 操作と全武器の技一覧（右クリックで開く）
// ===========================================================================
import { ActionFormData } from "@minecraft/server-ui";
import { WEAPONS } from "./config.js";

const CONTROLS = [
  "§l§6■ 基本操作§r",
  "§f攻撃（左クリック）§7… 当てるたびに 1→2→3 段目のコンボ。三段目は武器ごとの追撃",
  "§f右クリック§7 … 戦技",
  "§fダッシュ中に右クリック§7 … 突進技",
  "§f空中で右クリック§7 … 空中技",
  "§fスニーク＋右クリック§7 … 必殺技（超次元ゲージ 100% で発動）",
  "",
  "§l§6■ 機動§r",
  "§f空中でジャンプ§7 … 二段ジャンプ（双剣・ダガー・かぎ爪は三段）",
  "§f空中でスニーク§7 … 空中ダッシュ",
  "§f地上でスニークを素早く 2 回§7 … 回避ステップ（直後は無敵）",
  "§f武器を持ってダッシュ§7 … 加速（軽い武器ほど速い）",
  "§7技や機動で跳んだ後の落下ダメージは無効",
  "",
  "§l§6■ 超次元ゲージ§r",
  "§7攻撃を当てる・被弾する・ジャストガードで溜まる。満タンで HUD が金色に流れる",
  "",
  "§l§6■ 弓と盾§r",
  "§f弓§7 … 右クリックで引き、離して撃つ。0.4 秒で LV1、1 秒で LV2（三本の貫通矢）",
  "     §7空中で離すと「星雨」、ダッシュ中に引くと「宙返り三連射」",
  "§f盾§7 … 右クリックの間ガード。構えた直後 0.3 秒はジャストガード（無傷＋凍結反撃）",
  "     §7離すと、受けた衝撃を「氷撃反射」で返す",
];

const DESC = {
  greatsword: {
    skill: "溜めて振り下ろし、次元の裂け目を 12m 先まで走らせる",
    dash: "切先を突き出して駆け抜け、最後に炸裂",
    air: "宙で止まり、真下へ叩きつけて次元の柱を六本立てる",
    ult: "時を止め、空間ごと七度断ち、天から斬り落とす",
  },
  twinblades: {
    skill: "左右の刃で六連、十字で吹き飛ばす",
    dash: "竜巻をまとい回転しながら駆け抜ける",
    air: "前の敵へ急降下して十字に斬り、宙返りで離脱",
    ult: "周りの敵の間を風になって渡り斬り、竜巻で締める",
  },
  greataxe: {
    skill: "振り下ろした先で溶岩が三度噴き上がる",
    dash: "炎の輪をまとって回転しながら前進",
    air: "隕石のように落ち、着地点をクレーターに",
    ult: "五つの火口が噴き、最後に大地が爆ぜる",
  },
  dagger: {
    skill: "影の苦無を三本投げ、刺さった相手を縫い止める",
    dash: "前方の敵の背後へ瞬間移動して背中を斬る",
    air: "回りながら落ち、着地で影の刃を八方へ",
    ult: "夜に溶けて八方から斬り、紫の月で葬る",
  },
  bow: {
    skill: "引き絞って放つ光の矢（溜めで三段階）",
    dash: "後ろへ宙返りしながら三本を扇に放つ",
    air: "狙った地点に陣を描き、天から光の矢を降らせる",
    ult: "神弓の陣を展開し、極太の光線で貫く",
  },
  shield: {
    skill: "ガードで受けた衝撃を凍気の爆発にして返す",
    dash: "盾を前に突進し、触れた敵を弾いて凍らせる",
    air: "盾ごと落ちて氷の棘を二重の輪で突き上げる",
    ult: "氷の結界で身を守り、内の敵を凍らせて砕く",
  },
  whip: {
    skill: "9m 先まで届く二連の鞭打ち。茨で出血",
    dash: "敵に絡めて引き寄せる。敵がいなければ壁や地面へ飛び移る",
    air: "宙で鞭を振り回し、周り 5m を薔薇の渦で刻む",
    ult: "薔薇の陣に入った敵を茨で縛り、命を吸う",
  },
  claws: {
    skill: "左右交互の四連撃から、両爪の大十字",
    dash: "弧を描いて跳びかかり、組み伏せて裂く",
    air: "斬り上げで自分も敵も空へ打ち上げる",
    ult: "咆哮で薙ぎ払い、一体に十二連の乱撃",
  },
};

export function openGuide(player) {
  const list = Object.values(WEAPONS);
  const form = new ActionFormData()
    .title("§l超次元指南書")
    .body("§7超次元の武器を持って戦うための手引き。読みたい項目を選んでください。")
    .button("§l操作と機動", "textures/items/hd/guide");
  for (const w of list) form.button(`${w.tc}§l${w.short}\n§r§8${w.name}`, `textures/items/hd/${w.key}`);
  form.show(player).then((r) => {
    if (!r || r.canceled || r.selection === undefined) return;
    if (r.selection === 0) return page(player, "§l操作と機動", CONTROLS.join("\n"));
    const w = list[r.selection - 1];
    const lines = [`${w.tc}§l${w.name}§r`, ""];
    for (const k of ["skill", "dash", "air", "ult"]) {
      const mv = w.moves[k];
      const head = { skill: "戦技（右クリック）", dash: "突進技（ダッシュ中に右クリック）",
                     air: "空中技（空中で右クリック）", ult: "必殺技（スニーク＋右クリック）" }[k];
      lines.push(`§6${head}`);
      lines.push(`${w.tc}§l「${mv.name}」§r §7${mv.en}`);
      lines.push(`§f${DESC[w.key][k]}  §8再使用 ${(mv.cd / 20).toFixed(1)} 秒`);
      lines.push("");
    }
    return page(player, `${w.tc}§l${w.short}`, lines.join("\n"));
  }).catch(() => { });
}

function page(player, title, body) {
  new ActionFormData().title(title).body(body).button("§l戻る").show(player)
    .then((r) => { if (r && !r.canceled) openGuide(player); }).catch(() => { });
}
