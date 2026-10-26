// 偽の @minecraft/common 1.2.0（NIGHT RUNNER の挙動テスト用。test_nr.py が node_modules に置く）。
// d.ts（typings/common/index.d.ts）の実行時の名前はエラーの型 4 つだけ（NumberRange は interface）。
// 実機のエラーは new できないが、偽物は中で投げるために message を受け取る。

function errClass(name, fields) {
  const C = class extends Error {
    constructor(message) {
      super(message);
      this.name = name;
      for (const f of fields) this[f] = undefined;
    }
  };
  Object.defineProperty(C, "name", { value: name });
  return C;
}

export const ArgumentOutOfBoundsError = errClass("ArgumentOutOfBoundsError", ["maxValue", "minValue", "value"]);
export const EngineError = errClass("EngineError", []);
export const InvalidArgumentError = errClass("InvalidArgumentError", ["index"]);
export const PropertyOutOfBoundsError = errClass("PropertyOutOfBoundsError", ["maxValue", "minValue", "value"]);
