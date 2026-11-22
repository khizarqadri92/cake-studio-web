import { ErrorBox, Spinner } from "@/components/states";
import { useSeo } from "@/lib/theme";
import { useHomepage } from "@/lib/queries";
import { SECTION_COMPONENTS } from "./home/sections";

export default function Home() {
  const { data, isLoading, isError } = useHomepage();
  useSeo();
  if (isLoading) return <Spinner />;
  if (isError || !data) return <div className="mx-auto max-w-xl px-4 py-16"><ErrorBox /></div>;
  return (
    <>
      {data.sections.map((s) => {
        const C = SECTION_COMPONENTS[s.key];
        return C ? <C key={s.key} section={s} home={data} /> : null;
      })}
    </>
  );
}
