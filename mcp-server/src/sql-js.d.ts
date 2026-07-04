// Type declarations for sql.js WASM fallback
declare module "sql.js" {
  interface SqlJsStatic {
    Database: new (data?: ArrayLike<number> | Buffer | null) => Database;
  }

  interface Database {
    prepare(sql: string): Statement;
    close(): void;
  }

  interface Statement {
    bind(params?: unknown[]): boolean;
    step(): boolean;
    getColumnNames(): string[];
    get(): unknown[];
    free(): boolean;
  }

  export default function initSqlJs(config?: object): Promise<SqlJsStatic>;
}
