import { Suspense } from "react";

import {
  DocumentWorkbench,
  DocumentWorkbenchFallback,
} from "@/components/design-system/document-workbench";

export default function BillsPage() {
  return (
    <Suspense fallback={<DocumentWorkbenchFallback kind="bill" />}>
      <DocumentWorkbench kind="bill" />
    </Suspense>
  );
}
